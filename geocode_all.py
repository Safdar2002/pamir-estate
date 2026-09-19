"""Проходит по всем объектам без координат и геокодирует их адреса."""
from app import app, db
from models import Property
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

def geocode_address(address):
    geolocator = Nominatim(user_agent="pamir_estate_script (mazambekov.safdar@mail.ru)")
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f'⚠️ Ошибка: {e}')
    return None, None

with app.app_context():
    properties = Property.query.all()
    print(f'📋 Найдено объектов: {len(properties)}\n')

    updated = 0
    for prop in properties:
        if prop.latitude and prop.longitude:
            print(f'⏭️  #{prop.id} уже с координатами: {prop.title[:40]}')
            continue

        full_address = ', '.join(filter(None, [prop.city, prop.street, prop.address]))
        if not full_address.strip():
            print(f'⚠️  #{prop.id} нет адреса: {prop.title[:40]}')
            continue

        print(f'🔎 #{prop.id} Геокодируем: "{full_address}"')
        lat, lon = geocode_address(full_address)

        if lat and lon:
            prop.latitude = lat
            prop.longitude = lon
            db.session.commit()
            updated += 1
            print(f'   ✅ {lat}, {lon}')
        else:
            print(f'   ❌ Не удалось найти координаты')

        time.sleep(1)  # пауза, чтобы не забанили в Nominatim

    print(f'\n🎉 Обновлено объектов: {updated}')