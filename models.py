from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Property(db.Model):
    __tablename__ = 'properties'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(300), nullable=False)
    city = db.Column(db.String(100), nullable=True, index=True)
    metro = db.Column(db.String(100), nullable=True)
    street = db.Column(db.String(200), nullable=True)
    property_type = db.Column(db.String(50), nullable=False)
    rooms = db.Column(db.Integer, nullable=True)
    area = db.Column(db.Float, nullable=True)
    floor = db.Column(db.Integer, nullable=True)
    total_floors = db.Column(db.Integer, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    images = db.relationship('PropertyImage', backref='property',
                             cascade='all, delete-orphan',
                             order_by='PropertyImage.sort_order')

    def __repr__(self):
        return f'<Property {self.title}>'


class PropertyImage(db.Model):
    __tablename__ = 'property_images'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<PropertyImage {self.image_url}>'


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(50), nullable=True)
    property_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<Lead {self.name} {self.phone}>'