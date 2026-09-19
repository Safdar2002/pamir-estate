from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, Response, send_from_directory
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from functools import wraps
from models import db, Property, Lead, PropertyImage
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from sqlalchemy import inspect, text
import os
import uuid
import traceback

app = Flask(__name__)

# ============ БЕЗОПАСНЫЕ НАСТРОЙКИ ============

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production-please')

# ============ НАСТРОЙКИ БАЗЫ ДАННЫХ И ХРАНИЛИЩА ============

PERSISTENT_PATH = None
for path in ['/data', '/var/data']:
    if os.path.exists(path) and os.access(path, os.W_OK):
        PERSISTENT_PATH = path
        break

if PERSISTENT_PATH:
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{PERSISTENT_PATH}/pamir_estate.db'
    app.config['UPLOAD_FOLDER'] = os.path.join(PERSISTENT_PATH, 'uploads')
    print(f'✅ Используется постоянное хранилище: {PERSISTENT_PATH}')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pamir_estate.db'
    app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
    print('ℹ️ Локальный режим: база и загрузки в папке проекта')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Диагностика путей
print(f'📁 Рабочая директория: {os.getcwd()}')
print(f'📁 База данных: {app.config["SQLALCHEMY_DATABASE_URI"]}')
print(f'📁 Папка загрузок: {app.config["UPLOAD_FOLDER"]}')
print(f'📁 /data существует: {os.path.exists("/data")}')
print(f'📁 /data доступна для записи: {os.access("/data", os.W_OK) if os.path.exists("/data") else "нет"}')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============ НАСТРОЙКИ ПОЧТЫ ============

app.config['MAIL_SERVER'] = 'smtp.mail.ru'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'mazambekov.safdar@mail.ru')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'mazambekov.safdar@mail.ru')

# ============ НАСТРОЙКИ ЗАГРУЗКИ ФАЙЛОВ ============

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ============ ДАННЫЕ ДЛЯ ВХОДА В АДМИНКУ ============

app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admin123')

# ============ ИНИЦИАЛИЗАЦИЯ РАСШИРЕНИЙ ============

db.init_app(app)
mail = Mail(app)


# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def save_uploaded_image(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)

    if PERSISTENT_PATH:
        return f'/uploads/{unique_filename}'
    else:
        return f'/static/uploads/{unique_filename}'


def geocode_address(address):
    """Определяет координаты по адресу с помощью Nominatim (OpenStreetMap)."""
    if not address or not address.strip():
        return None, None

    geolocator = Nominatim(user_agent="pamir_estate_app (mazambekov.safdar@mail.ru)")
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            print(f'📍 Геокодировано: "{address}" → {location.latitude}, {location.longitude}')
            return location.latitude, location.longitude
        else:
            print(f'⚠️ Координаты для адреса "{address}" не найдены.')
            return None, None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f'⚠️ Ошибка геокодирования для "{address}": {e}')
        return None, None


def send_lead_email(name, phone, source='site', property_title=None):
    subject = '📩 Новая заявка с сайта PAMIR ESTATE'
    if property_title:
        subject += f' — {property_title}'
    body = f'Имя: {name}\nТелефон: {phone}\nИсточник: {source}'
    if property_title:
        body += f'\nОбъект: {property_title}'
    msg = Message(
        subject=subject,
        recipients=[app.config['MAIL_USERNAME']],
        body=body
    )
    mail.send(msg)


# ============ ОТДАЧА ЗАГРУЖЕННЫХ ФАЙЛОВ ============

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ============ SITEMAP ============

@app.route('/sitemap.xml')
def sitemap():
    """Карта сайта для поисковых систем."""
    pages = []
    for rule in ['index', 'catalog']:
        pages.append(url_for(rule, _external=True))
    for prop in Property.query.all():
        pages.append(url_for('property_detail', property_id=prop.id, _external=True))

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        sitemap_xml += f'   <url><loc>{page}</loc></url>\n'
    sitemap_xml += '</urlset>'
    return Response(sitemap_xml, mimetype='application/xml')


# ============ ПУБЛИЧНЫЕ МАРШРУТЫ ============

@app.route('/')
def index():
    new_buildings = Property.query.filter_by(property_type='new').limit(6).all()
    secondary = Property.query.filter_by(property_type='secondary').limit(6).all()
    country = Property.query.filter_by(property_type='country').limit(6).all()
    cities = [row[0] for row in db.session.query(Property.city).distinct().order_by(Property.city).all() if row[0]]
    return render_template('index.html',
                           new_buildings=new_buildings,
                           secondary=secondary,
                           country=country,
                           cities=cities)


@app.route('/catalog')
def catalog():
    property_type = request.args.get('type', '')
    city = request.args.get('city', '')
    metro = request.args.get('metro', '')
    street = request.args.get('street', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    rooms = request.args.get('rooms', type=int)

    query = Property.query
    if property_type:
        query = query.filter_by(property_type=property_type)
    if city:
        query = query.filter_by(city=city)
    if metro:
        query = query.filter(Property.metro.contains(metro))
    if street:
        query = query.filter(Property.street.contains(street))
    if min_price is not None:
        query = query.filter(Property.price >= min_price)
    if max_price is not None:
        query = query.filter(Property.price <= max_price)
    if rooms is not None:
        query = query.filter_by(rooms=rooms)

    cities = [row[0] for row in db.session.query(Property.city).distinct().order_by(Property.city).all() if row[0]]
    properties = query.order_by(Property.created_at.desc()).all()

    properties_data = [{
        'id': p.id,
        'title': p.title,
        'price': p.price,
        'address': p.address,
        'city': p.city,
        'latitude': p.latitude,
        'longitude': p.longitude,
        'image_url': p.image_url
    } for p in properties]

    return render_template('catalog.html',
                           properties=properties,
                           cities=cities,
                           properties_data=properties_data)


@app.route('/property/<int:property_id>')
def property_detail(property_id):
    prop = Property.query.get_or_404(property_id)
    return render_template('property_detail.html', property=prop)


@app.route('/api/properties')
def api_properties():
    properties = Property.query.all()
    return jsonify([{
        'id': p.id, 'title': p.title, 'price': p.price,
        'address': p.address, 'city': p.city, 'metro': p.metro,
        'property_type': p.property_type, 'rooms': p.rooms, 'area': p.area,
        'latitude': p.latitude, 'longitude': p.longitude
    } for p in properties])


@app.route('/api/consultation', methods=['POST'])
def consultation():
    data = request.get_json()
    name = data.get('name')
    phone = data.get('phone')
    source = data.get('source', 'main')
    property_id = data.get('property_id')

    if not name or not phone:
        return jsonify({'status': 'error', 'message': 'Заполните все поля'}), 400

    property_title = None
    if property_id:
        prop = Property.query.get(property_id)
        if prop:
            property_title = prop.title

    try:
        lead = Lead(name=name, phone=phone, source=source, property_id=property_id)
        db.session.add(lead)
        db.session.commit()
    except Exception as e:
        print(f'❌ Ошибка сохранения в БД: {e}')

    try:
        send_lead_email(name, phone, source, property_title)
        print(f'✅ Заявка отправлена: {name}, {phone}')
    except Exception as e:
        print(f'❌ Ошибка отправки письма: {e}')
        return jsonify({'status': 'error', 'message': 'Не удалось отправить заявку. Попробуйте позже.'}), 500

    return jsonify({'status': 'success', 'message': f'Спасибо, {name}! Мы свяжемся с вами.'})


# ============ АДМИН-ПАНЕЛЬ ============

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if (username == app.config['ADMIN_USERNAME'] and
                password == app.config['ADMIN_PASSWORD']):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_dashboard():
    properties = Property.query.order_by(Property.created_at.desc()).all()
    leads = Lead.query.order_by(Lead.created_at.desc()).limit(20).all()
    return render_template('admin/dashboard.html', properties=properties, leads=leads)


@app.route('/admin/property/new', methods=['GET', 'POST'])
@login_required
def admin_property_new():
    if request.method == 'POST':
        city = request.form.get('city', '')
        street = request.form.get('street', '')
        address = request.form.get('address', '')
        full_address = ', '.join(filter(None, [city, street, address]))
        lat, lon = geocode_address(full_address)

        main_image = save_uploaded_image(request.files.get('image'))
        prop = Property(
            title=request.form.get('title'),
            description=request.form.get('description'),
            price=float(request.form.get('price') or 0),
            city=city or None,
            address=address,
            metro=request.form.get('metro') or None,
            street=street or None,
            property_type=request.form.get('property_type'),
            rooms=int(request.form.get('rooms')) if request.form.get('rooms') else None,
            area=float(request.form.get('area')) if request.form.get('area') else None,
            floor=int(request.form.get('floor')) if request.form.get('floor') else None,
            total_floors=int(request.form.get('total_floors')) if request.form.get('total_floors') else None,
            latitude=lat,
            longitude=lon,
            image_url=main_image
        )
        db.session.add(prop)
        db.session.commit()

        extra_files = request.files.getlist('extra_images')
        for i, file in enumerate(extra_files):
            url = save_uploaded_image(file)
            if url:
                img = PropertyImage(property_id=prop.id, image_url=url, sort_order=i)
                db.session.add(img)
        db.session.commit()

        flash('Объект успешно добавлен', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/property_form.html', property=None)


@app.route('/admin/property/<int:property_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_property_edit(property_id):
    prop = Property.query.get_or_404(property_id)
    if request.method == 'POST':
        city = request.form.get('city', '')
        street = request.form.get('street', '')
        address = request.form.get('address', '')
        full_address = ', '.join(filter(None, [city, street, address]))
        lat, lon = geocode_address(full_address)

        prop.title = request.form.get('title')
        prop.description = request.form.get('description')
        prop.price = float(request.form.get('price') or 0)
        prop.city = city or None
        prop.address = address
        prop.metro = request.form.get('metro') or None
        prop.street = street or None
        prop.property_type = request.form.get('property_type')
        prop.rooms = int(request.form.get('rooms')) if request.form.get('rooms') else None
        prop.area = float(request.form.get('area')) if request.form.get('area') else None
        prop.floor = int(request.form.get('floor')) if request.form.get('floor') else None
        prop.total_floors = int(request.form.get('total_floors')) if request.form.get('total_floors') else None

        if lat and lon:
            prop.latitude = lat
            prop.longitude = lon

        new_image = save_uploaded_image(request.files.get('image'))
        if new_image:
            prop.image_url = new_image

        extra_files = request.files.getlist('extra_images')
        base_order = len(prop.images)
        for i, file in enumerate(extra_files):
            url = save_uploaded_image(file)
            if url:
                img = PropertyImage(property_id=prop.id, image_url=url, sort_order=base_order + i)
                db.session.add(img)

        db.session.commit()
        flash('Объект обновлён', 'success')
        return redirect(url_for('admin_property_edit', property_id=prop.id))

    return render_template('admin/property_form.html', property=prop)


@app.route('/admin/property/<int:property_id>/delete', methods=['POST'])
@login_required
def admin_property_delete(property_id):
    prop = Property.query.get_or_404(property_id)
    db.session.delete(prop)
    db.session.commit()
    flash('Объект удалён', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/image/<int:image_id>/delete', methods=['POST'])
@login_required
def admin_image_delete(image_id):
    img = PropertyImage.query.get_or_404(image_id)
    property_id = img.property_id
    db.session.delete(img)
    db.session.commit()
    flash('Фото удалено', 'success')
    return redirect(url_for('admin_property_edit', property_id=property_id))


# ============ ИНИЦИАЛИЗАЦИЯ И МИГРАЦИЯ БАЗЫ ============

def ensure_schema():
    """Добавляет отсутствующие колонки в существующие таблицы."""
    with app.app_context():
        inspector = inspect(db.engine)

        # Проверяем таблицу properties
        if 'properties' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('properties')]
            print(f'📋 Колонки в properties: {columns}')

            with db.engine.connect() as conn:
                if 'latitude' not in columns:
                    conn.execute(text('ALTER TABLE properties ADD COLUMN latitude FLOAT'))
                    print('✅ Добавлена колонка latitude')
                if 'longitude' not in columns:
                    conn.execute(text('ALTER TABLE properties ADD COLUMN longitude FLOAT'))
                    print('✅ Добавлена колонка longitude')
                conn.commit()
        else:
            print('ℹ️ Таблица properties ещё не создана — создастся через db.create_all()')

        # Проверяем таблицу leads
        if 'leads' in inspector.get_table_names():
            lead_columns = [col['name'] for col in inspector.get_columns('leads')]
            print(f'📋 Колонки в leads: {lead_columns}')


def init_db():
    """Создаёт БД, добавляет недостающие колонки и тестовые данные."""
    with app.app_context():
        # 1. Обновляем схему существующей БД
        ensure_schema()

        # 2. Создаём отсутствующие таблицы
        db.create_all()

        # 3. Наполняем тестовыми данными, если объектов нет
        if Property.query.count() == 0:
            sample_properties = [
                Property(title='Квартира в новостройке у метро Авиамоторная',
                         description='Просторная 2-комнатная квартира с панорамными окнами.',
                         price=12500000, address='ул. Авиамоторная, 10', city='Москва',
                         metro='Авиамоторная', street='Авиамоторная',
                         property_type='new', rooms=2, area=65.5, floor=10, total_floors=25,
                         latitude=55.7193, longitude=37.7126,
                         image_url='https://placehold.co/600x400?text=Новостройка'),
                Property(title='Вторичка на Автозаводской',
                         description='Уютная 1-комнатная квартира в кирпичном доме.',
                         price=8900000, address='ул. Автозаводская, 15', city='Москва',
                         metro='Автозаводская', street='Автозаводская',
                         property_type='secondary', rooms=1, area=38.0, floor=5, total_floors=9,
                         latitude=55.7071, longitude=37.6570,
                         image_url='https://placehold.co/600x400?text=Вторичка'),
                Property(title='Загородный дом в Подмосковье',
                         description='Двухэтажный дом с участком 10 соток.',
                         price=25000000, address='д. Ивановка', city='Московская область',
                         property_type='country', rooms=5, area=180.0,
                         latitude=55.7558, longitude=37.6173,
                         image_url='https://placehold.co/600x400?text=Загородный+дом'),
                Property(title='3-комнатная в новостройке у метро Академическая',
                         description='Квартира с отделкой под ключ.',
                         price=18500000, address='ул. Академическая, 5', city='Москва',
                         metro='Академическая', street='Академическая',
                         property_type='new', rooms=3, area=85.0, floor=8, total_floors=20,
                         latitude=55.6873, longitude=37.5732,
                         image_url='https://placehold.co/600x400?text=Новостройка+3к'),
                Property(title='Студия на Алексеевской',
                         description='Компактная студия для инвестиций.',
                         price=6500000, address='ул. Алексеевская, 20', city='Москва',
                         metro='Алексеевская', street='Алексеевская',
                         property_type='secondary', rooms=1, area=25.0, floor=3, total_floors=12,
                         latitude=55.8072, longitude=37.6384,
                         image_url='https://placehold.co/600x400?text=Студия'),
                Property(title='Квартира в центре Санкт-Петербурга',
                         description='Просторная 2-комнатная квартира рядом с Невским проспектом.',
                         price=14200000, address='Невский проспект, 50', city='Санкт-Петербург',
                         metro='Маяковская', street='Невский проспект',
                         property_type='secondary', rooms=2, area=72.0, floor=4, total_floors=7,
                         latitude=59.9343, longitude=30.3351,
                         image_url='https://placehold.co/600x400?text=СПб'),
                Property(title='Новостройка у метро Московская',
                         description='Современная 1-комнатная квартира в новом ЖК.',
                         price=9800000, address='Московский проспект, 180', city='Санкт-Петербург',
                         metro='Московская', street='Московский проспект',
                         property_type='new', rooms=1, area=42.0, floor=12, total_floors=18,
                         latitude=59.8518, longitude=30.3211,
                         image_url='https://placehold.co/600x400?text=СПб+Новостройка'),
                Property(title='Дом в Казани',
                         description='Просторный дом с участком в пригороде.',
                         price=12500000, address='ул. Загородная, 25', city='Казань',
                         property_type='country', rooms=4, area=150.0,
                         latitude=55.8304, longitude=49.0661,
                         image_url='https://placehold.co/600x400?text=Казань'),
            ]
            db.session.add_all(sample_properties)
            db.session.commit()
            print('✅ База данных инициализирована тестовыми данными.')
        else:
            print(f'ℹ️ База данных уже содержит {Property.query.count()} объектов.')


# ============ АВТОИНИЦИАЛИЗАЦИЯ ПРИ СТАРТЕ ============

with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f'⚠️ Ошибка инициализации БД: {e}')
        traceback.print_exc()


# ============ ЗАПУСК (локально) ============

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)