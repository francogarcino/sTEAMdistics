PACKAGES = [
    'model/modelo',
    'persistence/persistencia',
    'service/servicio',
    'test',
    'utils/otros',
    'controller',
]

PACKAGE_PATTERNS = [
    ('test',                     lambda p: 'src/test' in p),
    ('model/modelo',             lambda p: '/modelo/' in p or '/model/' in p),
    ('persistence/persistencia', lambda p: '/persistencia/' in p or '/persistence/' in p),
    ('service/servicio',         lambda p: '/servicios/' in p or '/service/' in p),
    ('controller',               lambda p: '/controller/' in p or '/controllers/' in p or '/webservice' in p),
    ('utils/otros',              lambda p: True),
]

GEMINI_MODELS = [
    ("v1beta", "gemini-2.5-flash"),
    ("v1beta", "gemini-2.0-flash"),
    ("v1beta", "gemini-2.0-flash-lite"),
]

MAX_DIFFS_PER_AUTHOR  = 15
MAX_COMMITS_FOR_AI    = 20
MAX_DIFF_CHARS        = 1500
MAX_TOTAL_DIFF_CHARS  = 10000
