import logging
import os
import json
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import threading
from flask_cors import CORS

# ============ إعدادات Flask ============
app = Flask(__name__)
CORS(app)

# إعدادات التخزين
REQUESTS_FILE = "requests.json"
PHOTOS_DIR = "photos"

# ============ إعدادات البوت ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تعريف مراحل المحادثة
NAME, PHOTO = range(2)

# إعدادات البوت (يجب تغييرها)
TOKEN = "ضع_توكن_البوت_هنا"
DEVELOPER_CHAT_ID = "ضع_chat_id_المطور_هنا"

# إنشاء المجلدات إذا لم تكن موجودة
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

if not os.path.exists(REQUESTS_FILE):
    with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)

# ============ دوال المساعدة ============
def bold_text(text):
    """تحويل النص إلى خط عريض باستخدام HTML"""
    if not text:
        return ""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<b>{text}</b>"

def save_request(request_data):
    """حفظ الطلب في ملف JSON"""
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        request_data['id'] = len(requests) + 1
        request_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        request_data['status'] = 'pending'  # pending, approved, rejected
        
        requests.append(request_data)
        
        with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(requests, f, ensure_ascii=False, indent=2)
        
        return request_data['id']
    except Exception as e:
        logger.error(f"خطأ في حفظ الطلب: {e}")
        return None

def update_request_status(request_id, status, notes=""):
    """تحديث حالة الطلب"""
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        for req in requests:
            if req['id'] == request_id:
                req['status'] = status
                req['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if notes:
                    req['notes'] = notes
                break
        
        with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(requests, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث الطلب: {e}")
        return False

# ============ دوال البوت ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    welcome_msg = (
        bold_text("مرحبا بك 👋") + "\n\n" +
        bold_text("1: إرسل الاسم التي تريد التطبيق يظهر به ✅❗") + "\n" +
        bold_text("2: إرسل الصوره التي تريد التطبيق يظهر بها ⚡") + "\n\n" +
        bold_text("وسيتم إنشاء تطبيق سحب الصور بنفس المواصفات اللي سترسلها ✅🥰")
    )
    
    await update.message.reply_text(
        welcome_msg,
        parse_mode=ParseMode.HTML
    )
    
    await update.message.reply_text(
        bold_text("إرسل الآن إسم التطبيق"),
        parse_mode=ParseMode.HTML
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال اسم التطبيق"""
    user_name = update.message.text
    context.user_data['app_name'] = user_name
    context.user_data['user_id'] = update.message.from_user.id
    context.user_data['username'] = update.message.from_user.username or "لا يوجد"
    context.user_data['first_name'] = update.message.from_user.first_name or "مجهول"
    context.user_data['chat_id'] = update.message.chat_id
    
    await update.message.reply_text(
        bold_text("تمام ✅") + "\n" + bold_text("إرسل الآن صورة التطبيق"),
        parse_mode=ParseMode.HTML
    )
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال صورة التطبيق"""
    try:
        # حفظ الصورة
        photo_file = await update.message.photo[-1].get_file()
        
        # إعداد البيانات
        user_data = context.user_data
        app_name = user_data.get('app_name', 'غير محدد')
        user_id = user_data.get('user_id', 'غير معروف')
        
        # اسم فريد للصورة
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        photo_filename = f"{user_id}_{timestamp}.jpg"
        photo_path = os.path.join(PHOTOS_DIR, photo_filename)
        
        await photo_file.download_to_drive(photo_path)
        
        # تحضير بيانات الطلب
        request_data = {
            'app_name': app_name,
            'user_id': user_id,
            'username': user_data.get('username'),
            'first_name': user_data.get('first_name'),
            'chat_id': user_data.get('chat_id'),
            'photo_filename': photo_filename,
            'photo_path': photo_path,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # حفظ الطلب
        request_id = save_request(request_data)
        
        # إعداد الرسالة للمطور
        message_to_dev = (
            bold_text("📦 طلب جديد لتطبيق سحب الصور") + "\n\n" +
            bold_text(f"🆔 رقم الطلب: {request_id}") + "\n" +
            bold_text(f"👤 المستخدم: {user_data.get('first_name')} (@{user_data.get('username')})") + "\n" +
            bold_text(f"🆔 ID المستخدم: {user_id}") + "\n" +
            bold_text(f"📱 اسم التطبيق المطلوب: {app_name}") + "\n\n" +
            bold_text("✅ تم استلام الطلب بنجاح")
        )
        
        # إرسال الطلب للمطور
        await context.bot.send_message(
            chat_id=DEVELOPER_CHAT_ID,
            text=message_to_dev,
            parse_mode=ParseMode.HTML
        )
        
        # إرسال الصورة للمطور
        with open(photo_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=DEVELOPER_CHAT_ID,
                photo=photo,
                caption=bold_text(f"📸 صورة التطبيق المطلوب: {app_name}"),
                parse_mode=ParseMode.HTML
            )
        
        # إرسال تأكيد للمستخدم
        await update.message.reply_text(
            bold_text("✅ تم إرسال طلبك بنجاح للمطور") + "\n" +
            bold_text(f"📋 رقم طلبك: {request_id}") + "\n" +
            bold_text("سيتم مراجعته والرد عليك قريباً"),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"حدث خطأ في get_photo: {e}")
        await update.message.reply_text(
            bold_text("❌ حدث خطأ أثناء معالجة طلبك"),
            parse_mode=ParseMode.HTML
        )
    
    # مسح بيانات المستخدم
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    await update.message.reply_text(
        bold_text("❌ تم إلغاء العملية"),
        parse_mode=ParseMode.HTML
    )
    context.user_data.clear()
    return ConversationHandler.END

# ============ واجهة Flask ============
@app.route('/', methods=['GET', 'HEAD'])
def index():
    """الصفحة الرئيسية"""
    if request.method == 'HEAD':
        return '', 200  # رد على طلبات HEAD بدون محتوى
    return '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>نظام إدارة طلبات تطبيقات سحب الصور</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                min-height: 100vh;
                color: #333;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            
            header {
                text-align: center;
                margin-bottom: 40px;
                padding-bottom: 20px;
                border-bottom: 2px solid #eee;
            }
            
            h1 {
                color: #2d3748;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .description {
                color: #4a5568;
                font-size: 1.1em;
                line-height: 1.6;
                margin-bottom: 30px;
            }
            
            .dashboard-links {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            
            .dashboard-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                text-decoration: none;
                color: inherit;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                border: 2px solid transparent;
            }
            
            .dashboard-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.2);
                border-color: #667eea;
            }
            
            .dashboard-card h3 {
                color: #2d3748;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .dashboard-card p {
                color: #718096;
                line-height: 1.6;
                margin-bottom: 0;
            }
            
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-top: 40px;
            }
            
            .stat-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }
            
            .stat-card h4 {
                margin-bottom: 10px;
                font-size: 1.1em;
                opacity: 0.9;
            }
            
            .stat-number {
                font-size: 2.5em;
                font-weight: bold;
                margin: 10px 0;
            }
            
            .api-info {
                background: #f7fafc;
                border-radius: 10px;
                padding: 20px;
                margin-top: 40px;
                border-left: 4px solid #4299e1;
            }
            
            .api-info h3 {
                color: #2d3748;
                margin-bottom: 15px;
            }
            
            code {
                background: #2d3748;
                color: #e2e8f0;
                padding: 5px 10px;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                display: block;
                margin: 10px 0;
                overflow-x: auto;
            }
            
            .instructions {
                background: #f0fff4;
                border-radius: 10px;
                padding: 25px;
                margin-top: 30px;
                border: 1px solid #c6f6d5;
            }
            
            .instructions h3 {
                color: #276749;
                margin-bottom: 15px;
            }
            
            .instructions ol {
                margin-right: 20px;
                line-height: 1.8;
            }
            
            @media (max-width: 768px) {
                .container {
                    padding: 15px;
                }
                
                h1 {
                    font-size: 2em;
                }
                
                .dashboard-links {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🤖 نظام إدارة طلبات تطبيقات سحب الصور</h1>
                <p class="description">
                    نظام متكامل لإدارة طلبات إنشاء تطبيقات سحب الصور من خلال بوت تليجرام مع لوحة تحكم ويب إدارية
                </p>
            </header>
            
            <div class="instructions">
                <h3>📋 تعليمات الاستخدام:</h3>
                <ol>
                    <li>تواصل مع البوت على تليجرام وأرسل <code>/start</code></li>
                    <li>اتبع التعليمات لإرسال اسم التطبيق وصورته</li>
                    <li>يمكنك متابعة حالة طلبك من خلال اللوحة الإدارية</li>
                    <li>ستصلك إشعارات عند تحديث حالة طلبك</li>
                </ol>
            </div>
            
            <div class="dashboard-links">
                <a href="/admin" class="dashboard-card">
                    <h3>📊 لوحة التحكم الإدارية</h3>
                    <p>عرض جميع الطلبات، تحديث الحالات، وإدارة التطبيقات المطلوبة</p>
                </a>
                
                <a href="/api/requests" class="dashboard-card">
                    <h3>🔧 واجهة برمجة التطبيقات (API)</h3>
                    <p>الوصول إلى بيانات الطلبات عبر API للدمج مع أنظمة أخرى</p>
                </a>
                
                <a href="/api/stats" class="dashboard-card">
                    <h3>📈 الإحصائيات والتحليلات</h3>
                    <p>عرض إحصائيات مفصلة عن الطلبات والأداء</p>
                </a>
            </div>
            
            <div class="stats" id="statsContainer">
                <!-- سيتم ملء الإحصائيات بواسطة JavaScript -->
            </div>
            
            <div class="api-info">
                <h3>🔗 نقاط API المتاحة:</h3>
                <p><strong>GET</strong> <code>/api/requests</code> - الحصول على جميع الطلبات</p>
                <p><strong>GET</strong> <code>/api/requests/{id}</code> - الحصول على طلب محدد</p>
                <p><strong>PUT</strong> <code>/api/requests/{id}/status</code> - تحديث حالة الطلب</p>
                <p><strong>GET</strong> <code>/api/stats</code> - إحصائيات الطلبات</p>
                <p><strong>GET</strong> <code>/photos/{filename}</code> - عرض الصور المحفوظة</p>
            </div>
        </div>
        
        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    
                    if (data.success) {
                        const stats = data.stats;
                        const statsHTML = `
                            <div class="stat-card">
                                <h4>📊 إجمالي الطلبات</h4>
                                <div class="stat-number">${stats.total}</div>
                            </div>
                            <div class="stat-card">
                                <h4>⏳ قيد الانتظار</h4>
                                <div class="stat-number">${stats.pending}</div>
                            </div>
                            <div class="stat-card">
                                <h4>✅ مقبولة</h4>
                                <div class="stat-number">${stats.approved}</div>
                            </div>
                            <div class="stat-card">
                                <h4>❌ مرفوضة</h4>
                                <div class="stat-number">${stats.rejected}</div>
                            </div>
                        `;
                        document.getElementById('statsContainer').innerHTML = statsHTML;
                    }
                } catch (error) {
                    console.error('Error loading stats:', error);
                    document.getElementById('statsContainer').innerHTML = 
                        '<div style="text-align: center; padding: 20px; color: #718096;">جاري تحميل الإحصائيات...</div>';
                }
            }
            
            // تحميل الإحصائيات عند فتح الصفحة
            document.addEventListener('DOMContentLoaded', loadStats);
            
            // تحديث الإحصائيات كل 30 ثانية
            setInterval(loadStats, 30000);
        </script>
    </body>
    </html>
    '''

@app.route('/api/requests', methods=['GET'])
def get_requests():
    """الحصول على جميع الطلبات"""
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        # إضافة مسار الصورة الكامل
        for req in requests:
            if 'photo_filename' in req:
                req['photo_url'] = f"/photos/{req['photo_filename']}"
        
        return jsonify({
            'success': True,
            'count': len(requests),
            'requests': requests
        })
    except Exception as e:
        logger.error(f"خطأ في جلب الطلبات: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/requests/<int:request_id>', methods=['GET'])
def get_request(request_id):
    """الحصول على طلب محدد"""
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        request_data = next((req for req in requests if req['id'] == request_id), None)
        
        if request_data:
            if 'photo_filename' in request_data:
                request_data['photo_url'] = f"/photos/{request_data['photo_filename']}"
            return jsonify({'success': True, 'request': request_data})
        else:
            return jsonify({'success': False, 'error': 'الطلب غير موجود'}), 404
    except Exception as e:
        logger.error(f"خطأ في جلب الطلب: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/requests/<int:request_id>/status', methods=['PUT'])
def update_status(request_id):
    """تحديث حالة الطلب"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'بيانات غير صالحة'}), 400
            
        status = data.get('status')
        notes = data.get('notes', '')
        
        if status not in ['pending', 'approved', 'rejected']:
            return jsonify({'success': False, 'error': 'حالة غير صالحة'}), 400
        
        # تحديث حالة الطلب في الملف
        success = update_request_status(request_id, status, notes)
        
        if success:
            # إرسال إشعار للمستخدم عبر البوت
            def send_notification():
                try:
                    with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
                        requests = json.load(f)
                    
                    req = next((r for r in requests if r['id'] == request_id), None)
                    if req and 'chat_id' in req:
                        # إنشاء تطبيق بوت جديد للإرسال
                        async def send_message():
                            try:
                                app = Application.builder().token(TOKEN).build()
                                
                                status_messages = {
                                    'approved': '✅ تم الموافقة على طلبك',
                                    'rejected': '❌ تم رفض طلبك',
                                    'pending': '🔄 طلبك قيد المراجعة'
                                }
                                
                                message = bold_text(status_messages.get(status, 'تم تحديث حالة طلبك'))
                                if notes:
                                    message += "\n" + bold_text(f"📝 ملاحظة: {notes}")
                                
                                await app.bot.send_message(
                                    chat_id=req['chat_id'],
                                    text=message,
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception as e:
                                logger.error(f"خطأ في إرسال الإشعار: {e}")
                        
                        # تشغيل الدالة غير المتزامنة
                        asyncio.run(send_message())
                except Exception as e:
                    logger.error(f"خطأ في إرسال الإشعار: {e}")
            
            # تشغيل الإشعار في خيط منفصل
            thread = threading.Thread(target=send_notification)
            thread.start()
            
            return jsonify({'success': True, 'message': 'تم تحديث الحالة بنجاح'})
        else:
            return jsonify({'success': False, 'error': 'فشل في تحديث الحالة'}), 500
            
    except Exception as e:
        logger.error(f"خطأ في تحديث الحالة: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/photos/<filename>')
def serve_photo(filename):
    """خدمة ملفات الصور"""
    try:
        return send_from_directory(PHOTOS_DIR, filename)
    except Exception as e:
        logger.error(f"خطأ في عرض الصورة: {e}")
        return "الصورة غير موجودة", 404

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """الحصول على إحصائيات الطلبات"""
    try:
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            requests = json.load(f)
        
        # حساب الإحصائيات
        total = len(requests)
        pending = len([r for r in requests if r.get('status') == 'pending'])
        approved = len([r for r in requests if r.get('status') == 'approved'])
        rejected = len([r for r in requests if r.get('status') == 'rejected'])
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = len([r for r in requests if r.get('created_at', '').startswith(today)])
        
        stats = {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'today': today_count
        }
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"خطأ في جلب الإحصائيات: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    """معالج الصفحات غير الموجودة"""
    return '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>404 - الصفحة غير موجودة</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                color: white;
                text-align: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
            }
            h1 {
                font-size: 4em;
                margin: 0;
            }
            a {
                color: white;
                text-decoration: none;
                background: rgba(255, 255, 255, 0.2);
                padding: 10px 20px;
                border-radius: 5px;
                margin-top: 20px;
                display: inline-block;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>404</h1>
            <p>الصفحة التي تبحث عنها غير موجودة</p>
            <a href="/">العودة للصفحة الرئيسية</a>
        </div>
    </body>
    </html>
    ''', 404

@app.errorhandler(500)
def internal_error(error):
    """معالج الأخطاء الداخلية"""
    logger.error(f"خطأ داخلي في الخادم: {error}")
    return jsonify({'success': False, 'error': 'خطأ داخلي في الخادم'}), 500

# ============ تشغيل البوت وFlask ============
def run_bot():
    """تشغيل بوت تليجرام"""
    # إنشاء تطبيق البوت
    application = Application.builder().token(TOKEN).build()
    
    # إعداد محادثة الطلبات
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # إضافة المعالج
    application.add_handler(conv_handler)
    
    # بدء البوت
    print("🤖 بوت تليجرام يعمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_flask():
    """تشغيل خادم Flask"""
    print("🌐 خادم ويب يعمل على http://localhost:5000")
    print("📊 لوحة التحكم الإدارية: http://localhost:5000/admin")
    print("🔧 API الطلبات: http://localhost:5000/api/requests")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # تشغيل البوت في خيط منفصل
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # تشغيل Flask في الخيط الرئيسي
    run_flask()
