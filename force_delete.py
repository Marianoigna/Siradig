import shutil, os
shutil.rmtree('extension/__pycache__', ignore_errors=True)
print('Eliminado:', not os.path.exists('extension/__pycache__'))
