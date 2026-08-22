import unittest

from app import (
    Temperature,
    celsius_to_fahrenheit,
    create_app,
    db,
)


class ApplicationUnitTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                'TESTING': True,
                'WTF_CSRF_ENABLED': False,
                'SQLALCHEMY_DATABASE_URI': 'sqlite://',
                'SQLALCHEMY_ENGINE_OPTIONS': {},
                'SECRET_KEY': 'unit-test-only-secret',
                'STUDENT': 'Unit Test Student',
                'COLLEGE': 'Unit Test College',
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_conversion_formula(self):
        cases = (
            (0, 32),
            (100, 212),
            (-40, -40),
            (36.666, 98.0),
        )
        for celsius, expected in cases:
            with self.subTest(celsius=celsius):
                self.assertEqual(celsius_to_fahrenheit(celsius), expected)

    def test_index_displays_title_and_test_identity(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<title>TempConverter</title>', response.data)
        self.assertIn(b'Unit Test Student', response.data)
        self.assertIn(b'Unit Test College', response.data)

    def test_valid_post_stores_conversion(self):
        response = self.client.post(
            '/',
            data={'celsius': '100', 'submit': 'Convert'},
            environ_base={
                'REMOTE_ADDR': '2001:db8:85a3::8a2e:370:7334',
                'HTTP_USER_AGENT': 'x' * 300,
            },
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            stored = db.session.execute(db.select(Temperature)).scalar_one()
            self.assertEqual(stored.celsius, 100)
            self.assertEqual(stored.fahrenheit, 212)
            self.assertEqual(
                stored.ip_address,
                '2001:db8:85a3::8a2e:370:7334',
            )
            self.assertEqual(stored.user_agent, 'x' * 255)

    def test_invalid_post_does_not_store_conversion(self):
        for invalid_value in ('', 'nan', 'inf', '-inf', '1e308', '-1e308'):
            with self.subTest(value=invalid_value):
                response = self.client.post(
                    '/',
                    data={
                        'celsius': invalid_value,
                        'submit': 'Convert',
                    },
                )

                self.assertEqual(response.status_code, 200)
                with self.app.app_context():
                    self.assertEqual(
                        db.session.scalar(
                            db.select(db.func.count()).select_from(Temperature)
                        ),
                        0,
                    )


if __name__ == '__main__':
    unittest.main()
