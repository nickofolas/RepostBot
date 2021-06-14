# TheReposterminator

> TheReposterminator has a userscript to make working with it even easer! [See here for more](#userscript)
    <br>
> [Install it here](https://github.com/nickofolas/TheReposterminator/raw/master/popout-viewer.user.js)

TheReposterminator is a Reddit bot made to detect reposts.

## Documentation
Documentation explaining everything about using and configuring TheReposterminator can be found [here](https://github.com/nickofolas/TheReposterminator/raw/master/doc).

## Userscript
TheReposterminator also has a userscript that can be used with extensions such as [Greasemonkey](https://www.greasespot.net/) or [Tampermonkey](https://www.tampermonkey.net/). It adds a new button to flagged posts that launches a small popout that shows the chart provided by TheReposterminator's comment, saving the hassle of opening the comments section for each post.

The userscript can be installed by clicking [here](https://github.com/nickofolas/TheReposterminator/raw/master/popout-viewer.user.js) with a userscript engine (i.e. Grease/Tampermonkey) installed on your browser.

## Self-hosting
I'd prefer that you don't run an instance of the bot, but I can't stop you, so here's a quick guide.

1. Install **Python3.9** or above, as it is required to run the bot at all.

    *At this point, I would highly recommend creating a `venv` to do all of your work in, as it will help avoid pollution of your system's global package space.*

2. Install the bot's dependencies, that is, `pip install -Ur requirements.txt`

3. Have a database set up, and with the `psql` tool, run:

    `\i schema.sql`

    This will create all necessary tables required to store the bot's data.

4. Create a copy of `example_config.toml`, and rename it to `config.toml`. Add the correct values to the file.

5. Have the Rust language installed on your system, and change directory into `image_hash`. Then, run `maturin build --release`. Once this completes, run `pip install target/wheels/image_hash*.whl` to install the image hashing package. Ensure that the wheel you install from uses the correct CPython version.

6. Run the bot

    To run the bot, simply navigate to the directory that `schema.sql` and `requirements.txt` installed themselves to, and run TheReposterminator as a Python module.

    `python -m TheReposterminator [arguments]`

    Available arguments for running TheReposterminator can be found by running `python -m TheReposterminator -h`
