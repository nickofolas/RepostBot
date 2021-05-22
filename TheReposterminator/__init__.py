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
import logging
from collections import namedtuple

import praw
import psycopg2
import toml
from prawcore import exceptions

from .interactive import Interactive
from .messages import MessageHandler
from .sentry import Sentry

# Define namedtuples
SubData = namedtuple("SubData", "subname indexed")

# Set up logging
logger = logging.getLogger(__name__)
formatting = "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
logging.basicConfig(
    format=formatting,
    level=logging.INFO,
    handlers=[logging.FileHandler("rterm.log", "w", "utf-8"),
              logging.StreamHandler()])


class BotClient:
    """The main Reposterminator object"""

    def __init__(self):
        self.sentry = Sentry(self)
        self.interactive = Interactive(self)
        self.message_handler = MessageHandler(self)

        self.subreddits = []
        self.subreddit_configs = {}

        self.config = self.load_config()
        self.default_sub_config = open("subreddit_config.toml", "r").read()
        self.setup_connections()
        self.update_subs()

    def load_config(self, fp="config.toml"):
        return toml.load(fp)

    def setup_connections(self):
        """Establishes a Reddit and database connection"""
        try:
            self.db = psycopg2.connect(
                **self.config["database"],
                connect_timeout=5
            )
            self.insert_cursor = self.db.cursor()

            self.reddit = praw.Reddit(**self.config["reddit"])

        except Exception as e:
            logger.critical(f"Connection setup failed; exiting: {e}")
            exit(1)

        else:
            logger.info(
                "✅ Reddit and database connections successfully established"
            )

    def run(self):
        """
        Runs the bot (this is blocking!)
        """

        self.get_all_configs() # This operation is very slow
        while True:
            if not self.subreddits:
                self.message_handler.handle()  # In case there are no subs

            for sub in self.subreddits:
                self.message_handler.handle()

                if not sub.indexed:
                    # Needs to be full-scanned first
                    self.sentry.scan_new_sub(sub)
                if sub.indexed:
                    # Scanned with intention of reporting now
                    self.sentry.scan_submissions(sub)

    def update_subs(self):
        """Updates the list of subreddits"""

        self.subreddits.clear()

        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM subreddits")
            for sub, indexed in cur.fetchall():
                self.subreddits.append(SubData(sub, indexed))
        self.db.commit()

        logger.debug("Updated list of subreddits")

    def get_all_configs(self):
        self.subreddit_configs.clear()

        for subname, indexed in self.subreddits:
            self.get_config(subname)

    def get_config(self, subname, ignore_errors=True):
        try:
            config_wiki = self.reddit.subreddit(subname) \
                .wiki["thereposterminator_config"]

            sub_config = toml.loads(
                config_wiki.content_md
            )
            template_config = toml.loads(self.default_sub_config)
            for key, value in template_config.items():
                if sub_config.get(key) is None:
                    sub_config.update({key: value})
            # ^ Update the value of the sub config with any
            # newly added keys, useful if a sub has an outdated
            # config

            for key, value in map(
                lambda k: (k, sub_config[k]),
                ["mentioned_threshold", "sentry_threshold"]
            ):
                if value < self.config["limits"]["minimum_threshold_allowed"]:

                    if ignore_errors:
                        sub_config[key] = template_config[key]
                    else:
                        raise ValueError(key)

        except (exceptions.NotFound, exceptions.Forbidden) as e:
            if ignore_errors:
                sub_config = toml.loads(self.default_sub_config)
            else:
                raise e

        logger.debug(f"Loaded config for r/{subname}: {sub_config}")
        self.subreddit_configs[subname] = sub_config

    def get_sub(self, subname):
        try:
            return next(filter(
                lambda sub: sub.subname.lower() == subname.lower(),
                self.subreddits
            ))
        except StopIteration:
            return None

    def reply(self, content, *, target):
        content += self.config["templates"]["bot_notice"]
        return target.reply(content)
