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
import operator
from collections import namedtuple
from datetime import datetime

from image_hash.image_hash import compare_hashes

MediaData = namedtuple("MediaData", "hash id subname")
Match = namedtuple("Match", "hash id subname similarity")

logger = logging.getLogger(__name__)


class Interactive:
    """
    Interactive module of TheReposterminator.

    Receives u/ mentions, and will act accordingly.
    """

    def __init__(self, bot):
        self.bot = bot

    def receive_mention(self, message):
        if not (sub := self.bot.get_sub(str(message.subreddit))):
            return
            # For the time being, ignore any subs that aren't indexed
            # Hopefully to prevent annoyance and stuff
    
        if not (
            message.body.split("u/")[-1].lower()
            == self.bot.config["reddit"]["username"].lower()
        ):
            return

        self.handle_requested_submission(  # TODO: Remove kwarg necessity?
            message=message,               # Alternative TODO: argparse the mention
            sub=sub,
            submission=message.submission
        )

    def handle_requested_submission(self, *, message, sub, submission):
        if submission.is_self:
            return

        cur = self.bot.db.cursor()
        cur.execute(
            "SELECT * FROM media_storage WHERE submission_id=%s",
            (submission.id,)
        )
        if not (data := cur.fetchone()):
            return
            # TODO: Make this more informative on front end
            # I don't want to - Nick
        cur.close()
        self.bot.db.commit()

        parent_data = MediaData(*data)

        def get_matches():
            # This is the same generator as in sentry.py (lazy)
            # TODO: Make sure this isn't taxing
            media_cursor = self.bot.db.cursor("fetch_media_requested")
            media_cursor.execute(
                """
                SELECT * FROM
                    media_storage
                WHERE
                    subname=%s AND
                    NOT submission_id=%s""",
                (parent_data.subname, submission.id)
            )

            for item in media_cursor:
                post = MediaData(*item)
                compared = compare_hashes(parent_data.hash, post.hash)
                if compared >= (
                    self.bot.subreddit_configs
                    [parent_data.subname]
                    ["mentioned_threshold"]
                ):
                    yield Match(*post, compared)

            media_cursor.close()
            self.bot.db.commit()

        if (matches := [*get_matches()]):
            matches = sorted(  # Sorts by confidence
                matches,
                key=operator.attrgetter("similarity"),
                reverse=True
            )[:100]
            self.do_response(
                message=message,
                submission=submission,
                matches=matches
            )

        else:
            self.bot.reply(
                "Couldn't find any matches - this post could be unique",
                target=message
            )
            logger.info(
                f"✅ https://redd.it/{submission.id} | "
                f"{('r/' + str(submission.subreddit)).center(24)} | "
                f"Unique - Requested by user")

    def do_response(self, *, message, submission, matches):
        rows = ""
        matches_posts = []

        # Request the posts in bulk
        for post in self.bot.reddit.info(map(lambda m: f"t3_{m.id}", matches)):
            match = next(filter(lambda m: m.id == post.id, matches))
            matches_posts.append((match, post))

        for match, post in matches_posts:
            if post.removed:
                cur_status = "Removed"
            elif getattr(post.author, "name", "[deleted]") == "[deleted]":
                cur_status = "Deleted"
            else:
                cur_status = "Active"

            created_at = datetime.fromtimestamp(post.created_utc)
            row = self.bot.config["templates"]["row_mentioned"].format(
                created_at.strftime("%a, %b %d, %Y at %H:%M:%S UTC"),
                post.url,
                post.title,
                post.id,
                cur_status,
                match.similarity
            )

            if len(rows + row) > 2500:
                break
            rows += row

        self.bot.reply(
            self.bot.config["templates"]["info_mentioned"].format(rows),
            target=message
        )

        logger.info(
            f"✅ https://redd.it/{submission.id} | "
            f"{('r/' + str(submission.subreddit)).center(24)} | "
            f"{len(matches)} matches | "
            f"[Requested by user]")
