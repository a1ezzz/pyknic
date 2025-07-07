
import argparse
import asyncio

from pyknic.lib.bellboy.app import BellboyCLIApp
from pyknic.lib.bellboy.error import BellboyCLIError


class Bellboy:

    __instance__ = None

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog='bellboy',
            description='A client for the pyknic server'
        )
        parser.add_argument('-v', '--verbose', action='count', default=0, help='more flags more logs')
        parser.add_argument('-u', '--url', type=str, required=True, help='pyknic server url')
        parser.add_argument('-t', '--token', type=str, help='pyknic access token')
        parser.add_argument('-c', '--config', type=str, help='configuration file')

        return parser

    @classmethod
    def main(cls) -> None:
        args = cls.parser().parse_args()
        cls.__instance__ = BellboyCLIApp(args.url, log_level=args.verbose, config_file=args.config, token=args.token)
        loop = asyncio.new_event_loop()

        try:
            loop.run_until_complete(cls.__instance__.start())
        except BellboyCLIError:
            pass


if __name__ == "__main__":
    Bellboy.main()
