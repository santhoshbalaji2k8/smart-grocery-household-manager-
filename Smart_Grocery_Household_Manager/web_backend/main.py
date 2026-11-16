from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
from pathlib import Path
import os, sys, base64, hashlib, hmac, secrets, time, json, re
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Database

DB_PATH = os.getenv('DATABASE_PATH', str(Path(__file__).resolve().parents[1] / 'smart_grocery.db'))
db = Database(DB_PATH)
with db.connect() as _con:
 _con.execute('CREATE TABLE IF NOT EXISTS web_owner (id INTEGER PRIMARY KEY CHECK(id=1), email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
AUTH_SECRET = os.getenv('AUTH_SECRET', 'development-only-change-this-secret')
OWNER_SETUP_KEY = os.getenv('OWNER_SETUP_KEY', 'local-only-setup-key-change-me')
TOKEN_TTL = 60 * 60 * 12
app = FastAPI(title='Smart Grocery & Household Manager API', version='1.0.0')
origins = [x.strip() for x in os.getenv('CORS_ORIGINS', '*').split(',') if x.strip()]
if os.getenv('RENDER_SERVICE_ID') and AUTH_SECRET == 'development-only-change-this-secret':
 raise RuntimeError('Set AUTH_SECRET to a unique random value before deploying.')
if os.getenv('RENDER_SERVICE_ID') and '*' in origins:
 raise RuntimeError('Set CORS_ORIGINS to the exact Netlify site origin before deploying.')
if os.getenv('RENDER_SERVICE_ID') and OWNER_SETUP_KEY == 'local-only-setup-key-change-me':
 raise RuntimeError('Set OWNER_SETUP_KEY before deploying so a stranger cannot claim the first owner account.')
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['*'], allow_headers=['*'])

def _password_hash(password: str) -> str:
 if len(password) < 12 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
  raise HTTPException(400, 'Use a password with at least 12 characters, including letters and numbers.')
 salt=secrets.token_bytes(16)
 digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310000)
 return base64.urlsafe_b64encode(salt).decode()+'.'+base64.urlsafe_b64encode(digest).decode()

def _verify_password(password: str, stored: str) -> bool:
 try:
  salt_s,digest_s=stored.split('.',1); salt=base64.urlsafe_b64decode(salt_s); expected=base64.urlsafe_b64decode(digest_s)
  actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000)
  return hmac.compare_digest(actual,expected)
 except Exception: return False

def _token(email: str) -> str:
 payload=base64.urlsafe_b64encode(json.dumps({'sub':email,'exp':int(time.time())+TOKEN_TTL},separators=(',',':')).encode()).decode().rstrip('=')
 sig=base64.urlsafe_b64encode(hmac.new(AUTH_SECRET.encode(),payload.encode(),hashlib.sha256).digest()).decode().rstrip('=')
 return payload+'.'+sig

def _valid_token(token: str) -> bool:
 try:
  payload,sig=token.split('.',1)
  expected=base64.urlsafe_b64encode(hmac.new(AUTH_SECRET.encode(),payload.encode(),hashlib.sha256).digest()).decode().rstrip('=')
  if not hmac.compare_digest(sig,expected): return False
  data=json.loads(base64.urlsafe_b64decode(payload+'='*((4-len(payload)%4)%4)))
  return int(data.get('exp',0)) > int(time.time()) and bool(db.one('SELECT id FROM web_owner WHERE email=?',(data.get('sub'),)))
 except Exception: return False

@app.middleware('http')
async def require_owner_auth(request: Request, call_next):
 path=request.url.path
 public = path in {'/api/health','/api/auth/status','/api/auth/register','/api/auth/login'} or path.startswith('/docs') or path.startswith('/openapi') or path.startswith('/redoc')
 if path.startswith('/api/') and not public and request.method != 'OPTIONS':
  header=request.headers.get('authorization','')
  if not header.startswith('Bearer ') or not _valid_token(header[7:]):
   from starlette.responses import JSONResponse
   return JSONResponse({'detail':'Please sign in to access this household.'},status_code=401)
 return await call_next(request)

@app.get('/api/auth/status')
def auth_status():
 owner=db.one('SELECT id FROM web_owner WHERE id=1')
 return {'setup_required':owner is None}

class AuthPayload(BaseModel):
 email: str
 password: str
 setup_key: str | None = None

@app.post('/api/auth/register')
def register_owner(p: AuthPayload):
 if not p.setup_key or not hmac.compare_digest(p.setup_key, OWNER_SETUP_KEY):
  raise HTTPException(403,'The owner setup key is missing or incorrect.')
 email=p.email.strip().lower()
 if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email): raise HTTPException(400,'Enter a valid email address.')
 hashed=_password_hash(p.password)
 try:
  with db.connect() as c:
   if c.execute('SELECT 1 FROM web_owner LIMIT 1').fetchone(): raise HTTPException(403,'Owner account already exists. Public registration is disabled.')
   c.execute('INSERT INTO web_owner(id,email,password_hash) VALUES(1,?,?)',(email,hashed))
 except HTTPException: raise
 except Exception: raise HTTPException(409,'Owner account already exists.')
 return {'access_token':_token(email),'token_type':'bearer','email':email}

@app.post('/api/auth/login')
def login_owner(p: AuthPayload):
 email=p.email.strip().lower(); owner=db.one('SELECT email,password_hash FROM web_owner WHERE id=1')
 if not owner or owner['email'] != email or not _verify_password(p.password,owner['password_hash']):
  raise HTTPException(401,'Email or password is incorrect.')
 return {'access_token':_token(email),'token_type':'bearer','email':email}
class Payload(BaseModel):
    data: dict[str, Any] = {}

TABLES = {
 'products': "SELECT p.*, c.name category, s.name store FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN stores s ON s.id=p.store_id ORDER BY p.name",
 'members': 'SELECT * FROM household_members ORDER BY name',
 'purchases': "SELECT p.*,s.name store,m.name member FROM purchases p LEFT JOIN stores s ON s.id=p.store_id LEFT JOIN household_members m ON m.id=p.member_id ORDER BY p.purchase_date DESC,p.id DESC",
 'expenses': "SELECT e.*,m.name member FROM expenses e LEFT JOIN household_members m ON m.id=e.member_id ORDER BY e.expense_date DESC,e.id DESC",
 'budgets': 'SELECT * FROM budgets ORDER BY start_date DESC',
 'shopping': 'SELECT * FROM shopping_lists ORDER BY list_date DESC,id DESC',
 'stores': 'SELECT * FROM stores ORDER BY name',
 'batches': "SELECT b.*,p.name product,p.unit FROM product_batches b JOIN products p ON p.id=b.product_id ORDER BY CASE WHEN b.expiry_date IS NULL THEN 1 ELSE 0 END,b.expiry_date",
 'notifications': 'SELECT * FROM notifications ORDER BY created_at DESC,id DESC',
 'prices': "SELECT h.*,p.name product,s.name store FROM price_history h JOIN products p ON p.id=h.product_id JOIN stores s ON s.id=h.store_id ORDER BY recorded_date DESC,id DESC",
 'waste': "SELECT w.*,p.name product,p.unit FROM waste_records w JOIN products p ON p.id=w.product_id ORDER BY waste_date DESC,id DESC",
}
def rows(sql, params=()): return [dict(r) for r in db.rows(sql, params)]
def one(sql, params=()):
 r=db.one(sql,params); return dict(r) if r else None
def safe(fn, *args):
 try: return fn(*args)
 except (ValueError, TypeError) as e: raise HTTPException(400, str(e))
 except Exception as e: raise HTTPException(400, str(e))
@app.get('/api/health')
def health(): return {'ok': True, 'app':'Smart Grocery & Household Manager'}
@app.get('/api/{resource}')
def list_resource(resource: str):
 if resource == 'dashboard':
  return {
   'total_products': db.one('SELECT COUNT(*) n FROM products')['n'],
   'low_stock': db.one('SELECT COUNT(*) n FROM products WHERE quantity>0 AND quantity<=min_quantity')['n'],
   'out_of_stock': db.one('SELECT COUNT(*) n FROM products WHERE quantity<=0')['n'],
   'top_category': db.one("SELECT c.name,COUNT(*) n FROM products p LEFT JOIN categories c ON c.id=p.category_id GROUP BY c.id ORDER BY n DESC LIMIT 1"),
   'products': rows(TABLES['products']), 'recent_purchases': rows(TABLES['purchases'])[:5],
   'recent_expenses': rows(TABLES['expenses'])[:5], 'expiring': rows("SELECT b.*,p.name product,p.unit FROM product_batches b JOIN products p ON p.id=b.product_id WHERE b.quantity>0 AND b.expiry_date IS NOT NULL ORDER BY b.expiry_date LIMIT 8")}
 if resource == 'reports':
  return {'category_spending':rows("SELECT category,SUM(CAST(amount AS REAL)) total FROM expenses GROUP BY category ORDER BY total DESC"), 'monthly_spending':rows("SELECT substr(expense_date,1,7) month,SUM(CAST(amount AS REAL)) total FROM expenses GROUP BY month ORDER BY month DESC LIMIT 12"), 'stock_by_category':rows("SELECT COALESCE(c.name,'Other') category,SUM(p.quantity) quantity FROM products p LEFT JOIN categories c ON c.id=p.category_id GROUP BY category")}
 if resource not in TABLES: raise HTTPException(404,'Unknown resource')
 return rows(TABLES[resource])
@app.post('/api/products')
def add_product(p:Payload): return {'id':safe(db.add_product,p.data)}
@app.put('/api/products/{pid}')
def edit_product(pid:int,p:Payload): safe(db.update_product,pid,p.data); return {'ok':True}
@app.delete('/api/products/{pid}')
def delete_product(pid:int): safe(db.delete_product,pid); return {'ok':True}
@app.post('/api/members')
def add_member(p:Payload): return {'id':safe(db.add_member,p.data)}
@app.put('/api/members/{mid}')
def edit_member(mid:int,p:Payload): safe(db.update_member,mid,p.data); return {'ok':True}
@app.post('/api/purchases')
def purchase(p:Payload): return {'id':safe(db.create_purchase,p.data)}
@app.delete('/api/purchases/{pid}')
def remove_purchase(pid:int): safe(db.delete_purchase,pid); return {'ok':True}
@app.post('/api/expenses')
def add_expense(p:Payload): return {'id':safe(db.add_expense,p.data)}
@app.put('/api/expenses/{eid}')
def edit_expense(eid:int,p:Payload): safe(db.update_expense,eid,p.data); return {'ok':True}
@app.delete('/api/expenses/{eid}')
def remove_expense(eid:int):
 with db.connect() as c:
  cur=c.execute('DELETE FROM expenses WHERE id=? AND purchase_id IS NULL',(eid,))
  if not cur.rowcount: raise HTTPException(400,'Expense not found or is linked to a purchase.')
 return {'ok':True}
@app.post('/api/shopping')
def add_list(p:Payload): return {'id':safe(db.add_shopping_list,p.data)}
@app.post('/api/shopping/items')
def add_shopping_item(p:Payload): return {'id':safe(db.add_shopping_item,p.data)}
@app.put('/api/shopping/items/{iid}')
def edit_shopping_item(iid:int,p:Payload): safe(db.update_shopping_item,iid,p.data); return {'ok':True}
@app.delete('/api/shopping/items/{iid}')
def remove_shopping_item(iid:int): safe(db.delete_shopping_item,iid); return {'ok':True}
@app.post('/api/stores')
def add_store(p:Payload): return {'id':safe(db.add_store,p.data)}
@app.post('/api/prices')
def add_price(p:Payload): return {'id':safe(db.add_price_record,p.data)}
@app.post('/api/budgets')
def add_budget(p:Payload): return {'id':safe(db.add_budget,p.data)}
@app.put('/api/budgets/{bid}')
def edit_budget(bid:int,p:Payload): safe(db.update_budget,bid,p.data); return {'ok':True}
@app.post('/api/consume/{pid}')
def consume(pid:int,p:Payload): safe(db.consume_stock,pid,p.data.get('quantity'),p.data.get('note','Consumption')); return {'ok':True}
@app.post('/api/waste')
def waste(p:Payload): safe(db.record_waste,p.data); return {'ok':True}
@app.post('/api/notifications/generate')
def generate_notifications(): db.generate_notifications(); return {'ok':True}
@app.post('/api/notifications/{nid}/read')
def read_notification(nid:int):
 with db.connect() as c: c.execute('UPDATE notifications SET is_read=1 WHERE id=?',(nid,))
 return {'ok':True}
@app.get('/api/settings')
def settings(): return {r['key']:r['value'] for r in db.rows('SELECT key,value FROM settings')}
@app.put('/api/settings')
def save_settings(p:Payload):
 for k,v in p.data.items():
  if k in {'theme','currency','language','date_format','budget_alert_thresholds'}: db.set_setting(k,v)
 return {'ok':True}

@app.get('/api/shopping/items')
def shopping_items(list_id:int):
 return rows("SELECT i.*,l.name list_name FROM shopping_list_items i JOIN shopping_lists l ON l.id=i.list_id WHERE i.list_id=? ORDER BY i.id",(list_id,))
@app.post('/api/shopping/items/{iid}/purchased')
def mark_shopping_purchased(iid:int,p:Payload):
 safe(db.mark_shopping_item_purchased,iid,p.data.get('actual_price',0)); return {'ok':True}
@app.post('/api/shopping/items/{iid}/convert')
def convert_shopping_item(iid:int,p:Payload):
 return {'id':safe(db.convert_shopping_item_to_purchase,iid,p.data.get('quantity'),p.data.get('unit_price'),p.data.get('purchase_date'),p.data.get('store_id'),p.data.get('member_id'),p.data.get('payment_method','Cash'))}
@app.put('/api/purchases/{pid}')
def edit_purchase(pid:int,p:Payload): safe(db.update_purchase,pid,p.data); return {'ok':True}
@app.post('/api/purchase-items/{item_id}/return')
def return_purchase_item(item_id:int,p:Payload):
 safe(db.return_purchase_item,item_id,p.data.get('quantity'),p.data.get('reason','Purchase return')); return {'ok':True}
@app.get('/api/price-comparison/{product_id}')
def price_comparison(product_id:int): return safe(db.price_comparison,product_id)
@app.get('/api/recurring')
def recurring(): return [dict(x) for x in db.recurring_schedules()]
@app.post('/api/recurring')
def add_recurring(p:Payload):
 d=p.data; return {'id':safe(db.create_recurring_schedule,d.get('name'),d.get('interval_days'),d.get('next_due'),d.get('items'))}
@app.put('/api/recurring/{sid}')
def toggle_recurring(sid:int,p:Payload): safe(db.set_recurring_schedule_active,sid,p.data.get('active')); return {'ok':True}
@app.post('/api/recurring/generate-due')
def generate_recurring(): return {'generated':safe(db.generate_due_recurring_lists)}



@app.put('/api/batches/{batch_id}')
def edit_batch(batch_id:int,p:Payload): safe(db.update_batch,batch_id,p.data); return {'ok':True}

@app.post('/api/budgets/{bid}/thresholds')
def budget_thresholds(bid:int,p:Payload): safe(db.set_budget_alert_thresholds,bid,p.data.get('thresholds',[])); return {'ok':True}

@app.get('/api/consumption-summary')
def consumption_summary(days:int=30):
 if days < 1 or days > 3660: raise HTTPException(400,'Days must be between 1 and 3660.')
 return safe(db.consumption_summary,days)

@app.get('/api/household-contributions')
def household_contributions(start_date:str,end_date:str):
 return safe(db.household_contributions,start_date,end_date)




@app.get('/api/purchases/{purchase_id}/items')
def purchase_items(purchase_id:int):
 if not db.one('SELECT id FROM purchases WHERE id=?',(purchase_id,)): raise HTTPException(404,'Purchase not found.')
 return rows("SELECT pi.*,p.name product,p.unit FROM purchase_items pi JOIN products p ON p.id=pi.product_id WHERE pi.purchase_id=? ORDER BY pi.id",(purchase_id,))

from io import BytesIO, StringIO
from fastapi.responses import StreamingResponse

EXPORT_QUERIES = {
 'products': TABLES['products'], 'purchases': TABLES['purchases'],
 'expenses': TABLES['expenses'], 'members': TABLES['members'],
 'shopping': TABLES['shopping'], 'batches': TABLES['batches'],
 'waste': TABLES['waste'], 'prices': TABLES['prices'],
}

@app.get('/api/export/{resource}/{file_format}')
def export_data(resource:str,file_format:str):
 if resource not in EXPORT_QUERIES: raise HTTPException(404,'This data type cannot be exported.')
 if file_format not in {'csv','xlsx','pdf'}: raise HTTPException(400,'Choose csv, xlsx or pdf.')
 data=rows(EXPORT_QUERIES[resource])
 headers=list(data[0].keys()) if data else ['No records']
 if file_format=='csv':
  import csv
  out=StringIO(); writer=csv.writer(out); writer.writerow(headers)
  for row in data: writer.writerow([row.get(k,'') for k in headers])
  payload=out.getvalue().encode('utf-8-sig'); media='text/csv'; ext='csv'
 elif file_format=='xlsx':
  from openpyxl import Workbook
  wb=Workbook(); ws=wb.active; ws.title=resource[:31].title(); ws.append(headers)
  for row in data: ws.append([row.get(k) for k in headers])
  for col in ws.columns:
   letter=col[0].column_letter; ws.column_dimensions[letter].width=min(max(max(len(str(c.value or '')) for c in col)+2,12),36)
  buf=BytesIO(); wb.save(buf); payload=buf.getvalue(); media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'; ext='xlsx'
 else:
  from reportlab.lib import colors
  from reportlab.lib.pagesizes import landscape, A4
  from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
  from reportlab.lib.styles import getSampleStyleSheet
  from xml.sax.saxutils import escape
  buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),rightMargin=22,leftMargin=22,topMargin=24,bottomMargin=24)
  styles=getSampleStyleSheet(); story=[Paragraph('Smart Grocery & Household Manager — '+escape(resource.title()),styles['Title']),Spacer(1,10)]
  matrix=[[Paragraph('<b>'+escape(str(h))+'</b>',styles['BodyText']) for h in headers]]
  for row in data: matrix.append([Paragraph(escape(str(row.get(k,'') if row.get(k) is not None else '')),styles['BodyText']) for k in headers])
  tbl=Table(matrix,repeatRows=1); tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E9F8F1')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#D8E1E8')),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)])); story.append(tbl); doc.build(story); payload=buf.getvalue(); media='application/pdf'; ext='pdf'
 return StreamingResponse(iter([payload]),media_type=media,headers={'Content-Disposition':f'attachment; filename="{resource}_report.{ext}"'})
