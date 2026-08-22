from datetime import datetime, timezone
from math import isfinite
from os import environ

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy import URL, text
from sqlalchemy.exc import SQLAlchemyError
from wtforms import FloatField, SubmitField
from wtforms.validators import InputRequired, ValidationError

db = SQLAlchemy()


def utc_now():
    """Return a naive UTC datetime suitable for SQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def database_uri_from_environment():
    """Build the database URI from the assignment environment variables."""
    database_url = environ.get('DATABASE_URL')
    if database_url:
        return database_url

    db_user = environ.get('DB_USER')
    db_pass = environ.get('DB_PASS')
    db_host = environ.get('DB_HOST')
    db_port = int(environ.get('DB_PORT', '3306'))
    db_name = environ.get('DB_NAME')

    missing = [
        name
        for name, value in {
            'DB_USER': db_user,
            'DB_PASS': db_pass,
            'DB_HOST': db_host,
            'DB_NAME': db_name,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            f'Missing required database configuration: {", ".join(missing)}'
        )

    return URL.create(
        drivername='mysql+pymysql',
        username=db_user,
        password=db_pass,
        host=db_host,
        port=db_port,
        database=db_name,
    )


class Temperature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    celsius = db.Column(db.Float, nullable=False)
    fahrenheit = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=utc_now)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(255), nullable=False)


def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit using the application's rounding rule."""
    return round((celsius * 1.8) + 32, 2)


def finite_temperature(_, field):
    """Reject values that are non-finite before or after conversion."""
    if field.data is None:
        return

    if (
        not isfinite(field.data)
        or not isfinite(celsius_to_fahrenheit(field.data))
    ):
        raise ValidationError('Enter a temperature within the supported range.')


def request_metadata(value, max_length):
    """Normalize bounded request metadata before storing it."""
    return ((value or '').strip()[:max_length] or 'unknown')


def user_agent_product(value):
    """Return a display-safe first user-agent token."""
    tokens = (value or '').split()
    return tokens[0] if tokens else 'unknown'


class TemperatureForm(FlaskForm):
    celsius = FloatField(
        'Celsius',
        validators=[InputRequired(), finite_temperature],
    )
    submit = SubmitField('Convert')


def create_app(test_config=None, initialize_database=True):
    app = Flask(__name__)

    test_config = test_config or {}
    database_uri = test_config.get('SQLALCHEMY_DATABASE_URI')
    if database_uri is None:
        database_uri = database_uri_from_environment()

    secret_key = test_config.get('SECRET_KEY', environ.get('SECRET_KEY'))
    if not secret_key:
        raise RuntimeError('SECRET_KEY must be configured')

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={'pool_pre_ping': True},
        STUDENT=environ.get('STUDENT', 'Default Student'),
        COLLEGE=environ.get('COLLEGE', 'Default College'),
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    @app.get('/health')
    def health():
        try:
            db.session.execute(text('SELECT 1'))
        except SQLAlchemyError:
            db.session.rollback()
            return {'status': 'unhealthy'}, 503
        return {'status': 'healthy'}, 200

    @app.route('/', methods=['GET', 'POST'])
    def index():
        form = TemperatureForm()
        if form.validate_on_submit():
            celsius = form.celsius.data
            temperature = Temperature(
                celsius=celsius,
                fahrenheit=celsius_to_fahrenheit(celsius),
                ip_address=request_metadata(request.remote_addr, 45),
                user_agent=request_metadata(request.user_agent.string, 255),
            )
            db.session.add(temperature)
            db.session.commit()

        temperatures = Temperature.query.order_by(
            Temperature.date.desc()
        ).limit(10).all()
        log_entries = [
            (
                temperature.date.strftime('%m/%d/%Y %I:%M:%S %p'),
                temperature.celsius,
                temperature.fahrenheit,
                temperature.ip_address,
                user_agent_product(temperature.user_agent),
            )
            for temperature in temperatures
        ]
        return render_template(
            'index.html',
            form=form,
            log_entries=log_entries,
            student=app.config['STUDENT'],
            college=app.config['COLLEGE'],
        )

    if initialize_database:
        with app.app_context():
            db.create_all()

    return app


if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=5000)
