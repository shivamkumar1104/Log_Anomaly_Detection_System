import importlib, traceback, sys
try:
    importlib.import_module('log_anomaly.api.visualization')
    print('Import success')
except Exception as e:
    print('Import failed')
    traceback.print_exc()

