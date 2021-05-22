"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2021 nickofolas

TheReposterminator is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

TheReposterminator is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with TheReposterminator.  If not, see <https://www.gnu.org/licenses/>.
"""
import argparse
import logging

from TheReposterminator import BotClient, logger

client = BotClient()

logging_level_mapping = {
    'info': logging.INFO,
    'debug': logging.DEBUG,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
    'notset': logging.NOTSET
}

parser = argparse.ArgumentParser(
    description='Provides tools to interact with and run the bot'
)
parser.add_argument(
    '-r', '--run',
    action='store_true',
    help='Runs the bot'
)
parser.add_argument(
    '-l', '--level',
    nargs='?',
    choices=['info', 'debug', 'warning', 'error', 'notset', 'critical'],
    help='Sets the logging level to use when running the bot'
)

args = parser.parse_args()


if args.level:
    logger.setLevel(logging_level_mapping[args.level])
    logger.info(f"Set logging level to {logging_level_mapping[args.level]}")

if args.run:
    client.run()
