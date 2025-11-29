from os import environ
SESSION_CONFIG_DEFAULTS = dict(real_world_currency_per_point=1.0, participation_fee=0.0)
SESSION_CONFIGS = [dict(name='pg_exo_const', num_demo_participants=20, app_sequence=['public_goods_firms'], formation_type='exogenous', returns_type='constant'), dict(name='pg_exo_incr', num_demo_participants=20, app_sequence=['public_goods_firms'], formation_type='exogenous', returns_type='increasing'), dict(name='pg_endo_const', num_demo_participants=18, app_sequence=['public_goods_firms'], formation_type='endogenous', returns_type='constant'), dict(name='pg_endo_incr', num_demo_participants=18, app_sequence=['public_goods_firms'], formation_type='endogenous', returns_type='increasing')]
LANGUAGE_CODE = 'en'
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = True
DEMO_PAGE_INTRO_HTML = ''
PARTICIPANT_FIELDS = []
SESSION_FIELDS = []
THOUSAND_SEPARATOR = ''
ROOMS = []

ADMIN_USERNAME = 'admin'
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

SECRET_KEY = 'blahblah'

# if an app is included in SESSION_CONFIGS, you don't need to list it here
INSTALLED_APPS = ['otree']


