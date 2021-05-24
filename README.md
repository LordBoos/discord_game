# Discord user game status Custom Component (for Home Assistant)

This component pulls information about user's status, and the game he's currently playing from the Discord.
It creates a sensor for every configured user with online status and game played status. Discord avatar is used as entity_picture.

You can use this component in combination with native Home Assistant Discord notify integration. It works well together, and you can use the 
same token for both components, and the bot will combine both functions. So 1 Discord bot to rule both.

## Configuration:

```yaml
sensor:
  - platform: discord_game
    token: secretDiscordBotToken
    image_format: webp            # optional, available formats are: png, webp, jpeg, jpg
    members:
      - 1234567890
      - 0987654321
      - 12345678900987654321
```

You have to create a Discord bot user and get it's token to be able to use this component.

To create a bot user and get a token:
1. Go to https://discordapp.com/developers/applications/
2. Create New Application
3. Put in a Name of your liking and click create
4. Click on Bot in the left panel and then Add Bot and Yes, do it!
5. A green message "A wild bot has appeared!" should appear on the page
6. Uncheck PUBLIC BOT
7. From roughly 26.10.2020 you have to also grant your bot Privileged Gateway Intents permissions.
8. Check Presence Intent
9. Check Server Members Intent
10. Click Save changes on the bottom of the page
11. Under Token, click on Copy
12. Now paste your token to the yaml configuration of HA replacing `secretDiscordBotToken` in the example above

You also need your own discord server (or some server where you have admin rights), and you need to invite the bot to that server.
To do that follow bellow steps:
1. Go to General information tab on your Discord bot developer page
2. Under Client ID, click Copy
3. Go to following URL (replace [CLIENT_ID] with id from previous step) https://discordapp.com/api/oauth2/authorize?client_id=[CLIENT_ID]&scope=bot&permissions=0
4. Select server to which you want to invite the bot and press Authorize

From now on, you can get status of every user on the same server the bot is in.
For every user you want the sensor for his user ID in the members section of yaml configuration.

To get user ID you need to perform following steps:
1. Open Discord
2. Go to User Settings (Cog icon next to your name in bottom left part of Discord window)
3. Go to Advanced
4. Enable Developer Mode
5. Close settings
6. Right click on any user on your Server that you want to Add to this integration
7. Select Copy

If you are using Safari or the iOS Home Assistant app, please set the `image_format` to `png`, because Safari doesn't support the `webp` image format.

Thanks to @descention https://github.com/descention for an original component idea and component itself which I've rewritten for current Discord
 API and Home Assistant and integrated it with HACS.
