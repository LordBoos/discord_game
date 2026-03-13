# Discord user game status Custom Component (for Home Assistant)

This component pulls information about user's status, and the game they're currently playing from the Discord.
It creates a sensor for every configured user with online status and game played status. Discord avatar is used as entity_picture.

You can use this component in combination with native Home Assistant Discord notify integration. It works well together, and you can use the 
same token for both components, and the bot will combine both functions. So 1 Discord bot to rule both.

## Configuration:

First you have to create a Discord bot user and get it's token to be able to use this component.

To create a bot user and get a token:
1. Go to https://discordapp.com/developers/applications/
2. Create New Application
3. Put in a Name of your liking and click create
4. In the Installation tab, change install link to None
5. Click on Bot in the left panel and then Add Bot and Yes, do it!
6. A green message "A wild bot has appeared!" should appear on the page
7. Uncheck PUBLIC BOT
8. Enable every Intent in the Privileged Gateway Intents section
9. Click Save changes on the bottom of the page
10. Under Token, click on Copy, this is your token, that you need to later paste into home assistant configuration flow, keep in mind that the bot first has to be invited to some server

You also need your own discord server (or some server where you have "manage server" permission), and you need to invite the bot to that server.
To invite your bot to your server, use following steps:
1. Go to General information tab on your Discord bot developer page
2. Under Client ID, click Copy
3. Go to following URL (replace [CLIENT_ID] with id from previous step) https://discordapp.com/api/oauth2/authorize?client_id=[CLIENT_ID]&scope=bot&permissions=0
4. Select server to which you want to invite the bot and press Authorize

If this doesn't work for you, you can try to use this guide to invite your bot (select no permissions): https://discordpy.readthedocs.io/en/stable/discord.html#inviting-your-bot

Now just go to Home Assistant integrations/devices dashboard and add Discord Game integration:
1. Paste your token
2. Select image format (only works for user avatars)
3. Optionally enter your Steam API key (see below)
4. On the next step select users that you want to track
5. If you want to use channel tracking which tracks which user last added a reaction, you can select channels, but this is optional and can be left blank.
6. Now continue and device for each user will be created with all the tracked sensors

## Steam API Key (optional)

A Steam API key is needed to load Steam game images (capsules, headers, logos, etc.) for the games your users are playing. Without it, only Discord-provided game images will be available.

To get a Steam API key:
1. Go to https://steamcommunity.com/dev/apikey
2. Log in with your Steam account
3. Enter a domain name (can be anything, e.g. `homeassistant.local`)
4. Accept the Steam Web API Terms of Use
5. Copy the key that is displayed

You can enter the key during initial setup, or add/change it later by going to the integration's page in Home Assistant and clicking **Configure**.


If you are using Safari or the iOS Home Assistant app, please set the `image_format` to `png`, because Safari doesn't support the `webp` image format.

Thanks to @descention https://github.com/descention for an original component idea and component itself which I've rewritten for current Discord
 API and Home Assistant and integrated it with HACS.
