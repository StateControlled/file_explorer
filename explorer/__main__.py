from explorer import __APP_PREF__
from explorer.exp import app

import explorer.save_data as save_data

def main():
    save_data.init()
    app(prog_name=__APP_PREF__)

if __name__ == '__main__':
    main()
