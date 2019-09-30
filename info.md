# Discord user game status Custom Component (for Home Assistant)

This component pulls information about user's status and the game he's currently playing from the Discord.

It creates a sensor for every configured user with online status and game played status. Discord avatar is used as entity_picture.

## Configuration:

```yaml
sensor:
  - platform: discord_game
    token: secretDiscordBotToken
    members:
      - Username1#1234
      - Username2#1234
```

You have to create a Discord bot user and get it's token to be able to use this component.

To create a bot user and get a token:
1. Go to https://discordapp.com/developers/applications/
2. Create New Application
3. Put in a Name of your liking and click create
4. Click on Bot in the left panel and then Add Bot and Yes, do it!
5. A green message "A wild bot has appeared!" should appear on the page
6. Uncheck PUBLIC BOT
7. Click Save changes on the bottom of the page
8. Under Token, click on Copy
9. Now paste your token to the yaml configuration of HA replacing "secretDiscordBotToken" in the example above

You also need your own discord server (or some server where you have admin rights) and you need to invite the bot to that server.
To do that follow bellow steps:
1. Go to General information tab on your Discord bot developer page
2. Under Client ID, click Copy
3. Go to following URL (replace [CLIENT_ID] with id from previous step) https://discordapp.com/api/oauth2/authorize?client_id=[CLIENT_ID]&scope=bot&permissions=0
4. Select server to which you want to invite the bot and press Authorize

From now on, you can get status of every user on the same server the bot is in.
For every user you want the sensor for, specify his username (including #XXXX) in the members section of yaml configuration.

Thanks to @descention https://github.com/descention for an original component idea and component itself which I've rewrote for current Discord
 API and Home Assistant and integrated it with HACS.
