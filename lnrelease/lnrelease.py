from faulthandler import dump_traceback_later

import parse
import scrape
import write


def main():
    dump_traceback_later(60*60*2, exit=True)
    scrape.main()
    parse.main()
    write.main()


if __name__ == '__main__':
    main()
