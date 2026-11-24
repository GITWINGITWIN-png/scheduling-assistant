# Setting up the Discord bot for เลขา (Secretary)

Do this once. It takes about 10 minutes. When it's done, เลขา creates 5 channels for you and talks with you in the #คุยกับเลขา (Chat with Secretary) channel. Everything lives in one server.

The bot makes **outbound** connections to Discord, so you don't need to open a port or a public URL on this machine. The bot only replies to you (based on the user id you enter in step 5).

## 1. Create a private server

In the Discord app, click **+** (Add a Server), choose **Create My Own**, then choose **For me and my friends**. Name it anything you like, for example "เลขา".

You don't need to create the channels yourself. The bot creates them in step 6.

## 2. Create the bot in the Developer Portal

1. Open https://discord.com/developers/applications, click **New Application**, and name it "เลขา".
2. On the **General Information** page, copy the **Application ID** and keep it. You'll use it in step 3.
3. On the **Bot** tab:
   - Click **Reset Token** and copy the token immediately. This page only shows it once.
   - Turn on **Message Content Intent** so the bot can read messages in the #ไอเดีย (Ideas) channel (used in B6).
   - Turn off **Public Bot** so that only you can invite the bot to the server.

## 3. Invite the bot to the server

Open this link, but replace `APP_ID` with the Application ID from step 2:

```
https://discord.com/oauth2/authorize?client_id=APP_ID&scope=bot&permissions=85008
```

Choose the server from step 1, then click Authorize.

The number `85008` is the set of permissions the bot uses: view channels; send messages; send cards (embeds); read message history; create channels (used during first setup).

## 4. Turn on Developer Mode to copy IDs

In Discord, go to User Settings → Advanced and turn on **Developer Mode**. Then:

- Right-click the server icon and choose **Copy Server ID**.
- Right-click your own name and choose **Copy User ID**.

## 5. Add the values to `backend/.env`

Add these 3 lines. The `.env` file is listed in .gitignore, so it won't leak into git:

```
SECRETARY_DISCORD_TOKEN=token-from-step-2
SECRETARY_DISCORD_GUILD_ID=server-id-from-step-4
SECRETARY_DISCORD_OWNER_ID=your-user-id-from-step-4
```

The token is the bot's password. If it leaks anywhere, click Reset Token in step 2 and enter the new value.

## 6. Restart เลขา and test

```
cd backend && uv run uvicorn app.main:app --port 8000
```

If you've set up the service (step 10), use `systemctl --user restart my-secretary` instead.

What you should see:

- The log has a line `discord ready as เลขา#…`
- The server has a category **เลขา** with the channels #คุยกับเลขา, #ด่วน (Urgent), #สรุป (Summary), #อนุมัติ (Approve), and #ไอเดีย.
- On the หน้าตั้งค่า (Settings page) at http://localhost:8000/settings, the Discord field shows "เชื่อมแล้ว" (Connected).

**Chat with เลขา:** type your question in the **#คุยกับเลขา** channel, for example "วันนี้เลขาทำอะไรไปบ้าง" (What did เลขา do today?). เลขา will answer with a reply message (reply).

The #general channel that Discord creates when you make the server isn't used by เลขา. You can delete it (right-click the channel → Delete Channel).

## If it doesn't connect

The settings page and the log state the cause in plain words:

| Message | What to do |
|---|---|
| ยังไม่ได้ตั้งค่า Discord (Discord is not set up yet) | The `.env` file doesn't have all 3 lines yet, or you haven't restarted. |
| token ของบอทไม่ถูกต้อง (The bot's token is invalid) | Copy a new token (Reset Token) |
| ยังไม่ได้เปิด Message Content Intent (Message Content Intent isn't turned on yet) | Turn it on in the Bot tab (step 2) |
| บอทยังไม่อยู่ในเซิร์ฟเวอร์ … (The bot isn't in the server yet …) | Open the invite link shown in the message, or the link in step 3. Check that the Server ID is correct. |
| บอทไม่มีสิทธิ์สร้างห้อง (The bot doesn't have permission to create channels) | Invite it again with the link in step 3 (it includes permissions=85008) |
| บอทไม่ตอบใน #คุยกับเลขา (The bot doesn't reply in #คุยกับเลขา) | Check that `SECRETARY_DISCORD_OWNER_ID` is **your** ID, not the bot's ID |
| Typing somewhere else (DM, #general, #ด่วน…) and the bot only tells you to go to #คุยกับเลขา | เลขา answers questions only in #คุยกับเลขา. The other channels in the category are where เลขา sends things to you. #ไอเดีย reads your messages starting from B6. |
