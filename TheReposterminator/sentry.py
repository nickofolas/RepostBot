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
from contextlib import suppress
from datetime import datetime
from io import BytesIO

import praw
import requests
from image_hash.image_hash import compare_hashes, generate_hash
from prawcore import exceptions

# Define namedtuples
MediaData = namedtuple("MediaData", "hash id subname")
Match = namedtuple("Match", "hash id subname similarity")

logger = logging.getLogger(__name__)


class Sentry:
    """
    Sentry module of TheReposterminator.

    Automatically scans /new/ of subreddits and leaves reports + comments.
    """

    def __init__(self, bot):
        self.bot = bot

        # Store problematic IDs in a cache to prevent recurring errors
        self.ignored_id_cache = set()

    @staticmethod
    def fetch_media(img_url):
        """Fetches submission media"""
        if not any(ext in img_url for ext in (".jpg", ".png", ".jpeg")):
            return False

        with requests.get(img_url) as resp:
            image_bytes = resp.content

            if len(image_bytes) < 89_478_485:
                return image_bytes
            else:
                logger.debug("Ignoring excessively large image")
                return False

    def handle_submission(self, submission, *, report):
        """Handles the submissions, deciding whether to index or report them"""
        if submission.is_self or submission.id in self.ignored_id_cache:
            return

        cur = self.bot.db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM indexed_submissions WHERE id=%s",
            (submission.id,)
        )
        if cur.fetchone()[-1] >= 1:
            self.bot.db.commit()  # Avoids "idle in transaction"
            return

        img_url = submission.url.replace("m.imgur.com", "i.imgur.com")

        try:
            if (media := self.fetch_media(img_url)) is False:
                return

            image_hash = generate_hash(media)
            if image_hash == 0:
                return  # This image couldn't be opened

            media_data = MediaData(
                str(image_hash),
                str(submission.id),
                str(submission.subreddit))

            def get_matches():
                # We're using a named cursor here because queries to
                # the media_storage table get massive in size, and the
                # memory allocated by a client-side cursor becomes
                # proportionally high
                media_cursor = self.bot.db.cursor("fetch_media")
                media_cursor.execute(
                    """
                    SELECT * FROM
                        media_storage
                    WHERE
                        subname=%s AND
                        NOT submission_id=%s""",
                    (media_data.subname, submission.id)
                )

                for item in media_cursor:
                    post = MediaData(*item)
                    compared = compare_hashes(media_data.hash, post.hash)
                    if compared >= (
                        self.bot.subreddit_configs
                        [media_data.subname]
                        ["sentry_threshold"]
                    ):
                        yield Match(*post, compared)

                media_cursor.close()
                self.bot.db.commit()

            if report:
                if (matches := [*get_matches()]):
                    matches = sorted(
                        matches,
                        key=operator.attrgetter("similarity"),
                        reverse=True
                    )[:25]
                    self.do_report(submission, matches)

            self.bot.insert_cursor.execute(
                "INSERT INTO media_storage VALUES(%s, %s, %s)",
                (*media_data,)
            )
            logger.debug(f"{submission.id} processed, added to media_storage")

        except Exception as e:

            logger.warn(f"Error processing submission {submission.id}: {e}")
            self.ignored_id_cache.add(submission.id)
            self.bot.db.commit()
            return

        finally:
            self.bot.insert_cursor.execute(
                "INSERT INTO indexed_submissions (id) VALUES (%s)",
                (submission.id,)
            )
            logger.debug(f"Added {submission.id} to indexed_submissions")
            cur.close()
            self.bot.db.commit()

    def do_report(self, submission, matches):
        """Executes reporting from a processed submission"""
        active = 0
        rows = ""
        matches_posts = []

        # Request the posts in bulk
        for post in self.bot.reddit.info(map(lambda m: f"t3_{m.id}", matches)):
            match = next(filter(lambda m: m.id == post.id, matches))
            matches_posts.append((match, post))

        for match, post in matches_posts:
            cur_score = int(post.score)

            if post.removed:
                cur_status = "Removed"
            elif getattr(post.author, "name", "[deleted]") == "[deleted]":
                cur_status = "Deleted"
            else:
                cur_status = "Active"
                active += 1

            created_at = datetime.fromtimestamp(post.created_utc)
            row = self.bot.config["templates"]["row_auto"].format(
                getattr(post.author, "name", "[deleted]"),
                created_at.strftime("%a, %b %d, %Y at %H:%M:%S UTC"),
                post.url,
                post.title,
                post.id,
                cur_score,
                cur_status,
                match.similarity
            )

            if len(rows + row) < 5000:
                rows += row

        submission.report(f"Possible repost ( {len(matches)} matches |"
                          f" {len(matches) - active} removed/deleted )")
        reply = self.bot.reply(
            self.bot.config["templates"]["info_auto"].format(rows),
            target=submission
        )

        with suppress(Exception):
            if (
                self.bot.subreddit_configs
                [str(submission.subreddit)]
                ["remove_sentry_comments"]
            ):
                praw.models.reddit.comment.CommentModeration(reply) \
                    .remove(spam=False)

        logger.info(
            f"✅ https://redd.it/{submission.id} | "
            f"{('r/' + str(submission.subreddit)).center(24)} | "
            f"{len(matches)} matches")

    def scan_submissions(self, sub):
        """Scans /new/ for an already indexed subreddit"""
        try:
            for submission in self.bot.reddit.subreddit(sub.subname).new():
                self.handle_submission(submission, report=True)

            logger.debug(f"Scanned r/{sub.subname} for new posts")

        except exceptions.Forbidden:  # In case bot is demodded mid-scan
            logger.debug(f"403'd mid scan on r/{sub.subname}, suppressing")

    def scan_new_sub(self, sub):
        """Performs initial indexing for a new subreddit"""
        for time in ("all", "year", "month"):  # TODO: Add 403 safeguard here
            for submission in self.bot.reddit.subreddit(sub.subname).top(
                time_filter=time
            ):
                logger.debug(
                    f"Indexing {submission.fullname} from r/{sub.subname}"
                )
                self.handle_submission(submission, report=False)

        with self.bot.db.cursor() as cur:
            cur.execute(
                "UPDATE subreddits SET indexed=TRUE WHERE name=%s",
                (sub.subname,)
            )

        self.bot.db.commit()
        logger.info(f"✅ Fully indexed r/{sub.subname}")
        self.bot.update_subs()
