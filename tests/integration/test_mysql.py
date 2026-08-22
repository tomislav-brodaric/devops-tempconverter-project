import os
import unittest

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import Temperature, create_app, db


TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')


def require_isolated_test_database(database_url):
    """Refuse destructive cleanup unless the dedicated test DB is selected."""
    parsed = make_url(database_url)
    if (
        parsed.get_backend_name() != 'mysql'
        or parsed.username != 'tempconverter_test'
        or parsed.database != 'tempconverter_test'
    ):
        raise RuntimeError(
            'TEST_DATABASE_URL must use the tempconverter_test MySQL '
            'database and tempconverter_test user'
        )


@unittest.skipUnless(
    TEST_DATABASE_URL,
    'TEST_DATABASE_URL is required for MySQL integration tests',
)
class MySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_test_database(TEST_DATABASE_URL)
        cls.app = create_app(
            {
                'TESTING': True,
                'WTF_CSRF_ENABLED': False,
                'SQLALCHEMY_DATABASE_URI': TEST_DATABASE_URL,
                'SECRET_KEY': 'integration-test-only-secret',
                'STUDENT': 'Integration Test Student',
                'COLLEGE': 'Integration Test College',
            }
        )
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def setUp(self):
        with self.app.app_context():
            db.session.execute(db.delete(Temperature))
            db.session.commit()

    def test_health_uses_non_root_mysql_connection(self):
        response = self.client.get('/health')

        with self.app.app_context():
            dialect = db.engine.dialect.name
            current_user = db.session.execute(
                text('SELECT CURRENT_USER()')
            ).scalar_one()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'healthy'})
        self.assertEqual(dialect, 'mysql')
        self.assertTrue(current_user.startswith('tempconverter_test@'))
        self.assertFalse(current_user.startswith('root@'))

    def test_post_persists_conversion_in_mysql(self):
        response = self.client.post(
            '/',
            data={'celsius': '100', 'submit': 'Convert'},
            environ_base={'REMOTE_ADDR': '127.0.0.1'},
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            stored = db.session.execute(db.select(Temperature)).scalar_one()
            self.assertEqual(stored.celsius, 100)
            self.assertEqual(stored.fahrenheit, 212)
            self.assertEqual(
                db.session.scalar(
                    db.select(db.func.count()).select_from(Temperature)
                ),
                1,
            )


if __name__ == '__main__':
    unittest.main()
