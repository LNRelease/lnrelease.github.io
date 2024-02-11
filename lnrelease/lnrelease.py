import parse
import scrape
import write


def main() -> None:
    scrape.main()
    parse.main()
    write.main()


if __name__ == '__main__':
    main()
