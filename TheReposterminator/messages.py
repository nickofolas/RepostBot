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

import toml
from prawcore import exceptions

logger = logging.getLogger(__name__)

class MessageHandler:

    def __init__(self, bot):
        self.bot = bot

        self.commands = {
            "update": self.command_update,
            "defaults": self.command_defaults
        }

    def handle(self):
        """Iterates over all unread messages and dispatches actions accordingly"""
        for message in self.bot.reddit.inbox.unread(mark_read=True):

            if "username mention" in message.subject.lower():
                if (
                    self.bot.subreddit_configs
                    [str(message.subreddit)]
                    ["respond_to_mentions"]
                ):
                    self.bot.interactive.receive_mention(message)

            if getattr(message, "subreddit", None):
                # Confirm that the message is from a subreddit
                if message.body.startswith(("**gadzooks!", "gadzooks!")) \
                        or "invitation to moderate" in message.subject:
                    self.accept_invite(message)
                elif "You have been removed as a moderator from " in message.body:
                    self.handle_mod_removal(message)

            else:
                if (command := self.commands.get(message.body.lower())):

                    if self.bot.get_sub(subname := message.subject.split("r/")[-1]):
                        self.run_command(command, subname, message)
                    
                    else:
                        message.reply("❌ I don't currently moderate this subreddit!")

            message.mark_read()

    # Mod invite handlers

    def accept_invite(self, message):
        """Accepts an invite to a new subreddit and adds it to the database"""
        message.subreddit.mod.accept_invite()
        self.bot.insert_cursor.execute(
            """
            INSERT INTO subreddits
            VALUES(
                %s,
                FALSE
            ) ON CONFLICT DO NOTHING""",
            (str(message.subreddit),)
        )
        self.bot.update_subs()

        self.bot.db.commit()
        logger.info(f"✅ Accepted mod invite to r/{message.subreddit}")

        try:
            message.subreddit.wiki["thereposterminator_config"].content_md
            # Avoid overwriting an existing wiki

        except exceptions.NotFound:
            message.subreddit.wiki.create(
                "thereposterminator_config",
                self.bot.default_sub_config,
                reason="Create TheReposterminator config"
            )

        except exceptions.Forbidden:
            return

        finally:
            self.bot.get_config(str(message.subreddit))

    def handle_mod_removal(self, message):
        """Handles removal from a subreddit"""
        self.bot.insert_cursor.execute(
            "DELETE FROM subreddits WHERE name=%s",
            (str(message.subreddit),)
        )
        self.bot.update_subs()

        self.bot.db.commit()
        logger.info(f"✅ Handled removal from r/{message.subreddit}")

    # DM commands

    def run_command(self, command, subname, message):
        # Check that the user actually mods the subreddit
        if not subname in [*map(str, message.author.moderated())]:
            message.reply(f"❌ You don't mod this subreddit!")

        command(subname, message)

    def command_update(self, subname, message):
        try:
            self.bot.get_config(subname, ignore_errors=False)
            message.reply("👍 Successfully updated your subreddit's config!")
            logger.info(f"✅ Config updated for r/{subname}")

        except exceptions.Forbidden:
            message.reply(
                "❌ Didn't have the permissions to access the wiki, "
                "no changes have been made"
            )

        except exceptions.NotFound:
            message.reply(
                "❌ No wiki page currently exists, no changes have been made"
            )

        except ValueError as error:
            message.reply(
                "❌ `{0}` was set to lower than its minimum allowed value of {1}, "
                "using its default value".format(
                    str(error),
                    self.bot.config["limits"]["minimum_threshold_allowed"]
                )
            )

        except Exception as e:
            message.reply("❌ Something went wrong, it'll be investigated")
            logger.error(f"Error in command update: {e}")

    def command_defaults(self, subname, message):
        try:
            self.bot.reddit.subreddit(subname).wiki.create(
                "thereposterminator_config",
                self.bot.default_sub_config,
                reason="Create/reset TheReposterminator config"
            )
            self.bot.subreddit_configs[subname] = toml.loads(self.bot.default_sub_config)
            message.reply("👍 Successfully created/reset your subreddit's config!")
            logger.info(f"✅ Config successfully created/reset for r/{subname}")

        except exceptions.Forbidden:
            message.reply(
                "❌ Didn't have the permissions to access the wiki, "
                "no changes have been made"
            )

        except Exception as e:
            message.reply("❌ Something went wrong, it'll be investigated")
            logger.error(f"Error in command defaults: {e}")
