import os
import sys

def main():
    # Si se invoca el comando test sin especificar --settings, usar por defecto config.settings.test
    if 'test' in sys.argv and not any(arg.startswith('--settings') for arg in sys.argv):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()