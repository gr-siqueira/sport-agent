# Sport Agent - User Guide

## Welcome to Sport Agent!

Sport Agent is your personal AI-powered sports assistant that delivers personalized daily sports digests. Never miss a game, score, or update for your favorite teams and players again!

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuring Your Interests](#configuring-your-interests)
3. [Generating Your Digest](#generating-your-digest)
4. [Understanding the Digest Format](#understanding-the-digest-format)
5. [How Scheduling Works](#how-scheduling-works)
6. [Managing Your Preferences](#managing-your-preferences)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

## Getting Started

### What You Need

To use Sport Agent, you need:
- Web browser (for the UI)
- Internet connection
- Your favorite teams, players, and leagues

That's it! No registration, no API keys required on your end.

### First Time Setup

1. **Open the Web Interface**
   - Navigate to http://localhost:8000 (or your server URL)
   - You'll see the Sport Agent homepage

2. **Configure Your Interests** (see next section)

3. **Generate Your First Digest**
   - Click "Generate Digest Now" to see a preview
   - Your digest will be automatically generated daily at your chosen time

## Configuring Your Interests

The Sport Agent needs to know what you care about to create your personalized digest.

### Required Information

#### 1. Favorite Teams
Enter your favorite teams as a comma-separated list.

**Examples:**
```
Lakers, Manchester United, Patriots
Golden State Warriors, Barcelona
Real Madrid, New York Yankees, Dallas Cowboys
```

**Tips:**
- Use commonly recognized team names
- You can follow teams from different sports
- No limit on number of teams (but 3-5 is optimal)

#### 2. Leagues/Sports
Specify which leagues or sports you follow.

**Examples:**
```
NBA, NFL, Premier League
MLB, La Liga, Champions League
NBA, NHL, NFL, MLS
```

**Supported Leagues:**
- Basketball: NBA, EuroLeague
- Football (Soccer): Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, MLS
- American Football: NFL, NCAA Football
- Baseball: MLB
- Hockey: NHL
- And more!

### Optional Information

#### 3. Favorite Players
Add specific players you want to track.

**Examples:**
```
LeBron James, Cristiano Ronaldo
Lionel Messi, Tom Brady, Aaron Judge
```

**What You'll Get:**
- Latest news about these players
- Injury updates and return timelines
- Recent performance statistics
- Transfer rumors and confirmations

#### 4. Delivery Time
Choose when you want your daily digest delivered.

**Default:** 7:00 AM
**Format:** 24-hour time (e.g., 07:00, 14:30, 22:00)

**Recommendations:**
- **Morning (7:00 AM):** Wake up to yesterday's results and today's schedule
- **Afternoon (12:00 PM):** Lunchtime catch-up on morning games
- **Evening (6:00 PM):** Pre-game briefing before prime-time matches

#### 5. Timezone
Select your local timezone for accurate game times.

**Popular Options:**
- Pacific Time (PT): America/Los_Angeles
- Mountain Time (MT): America/Denver
- Central Time (CT): America/Chicago
- Eastern Time (ET): America/New_York
- London (GMT/BST): Europe/London
- Paris (CET/CEST): Europe/Paris
- Tokyo (JST): Asia/Tokyo
- Sydney (AEST/AEDT): Australia/Sydney

## Generating Your Digest

### On-Demand Generation

After saving your preferences, you can generate a digest anytime:

1. Click "Generate Digest Now" button
2. Wait 5-10 seconds for processing
3. Your personalized digest appears on screen

**Use Cases:**
- Preview your digest before daily automation kicks in
- Get an update before heading to a game
- Check scores and schedule on your own timing

### Automated Daily Generation

Once you save your preferences, Sport Agent automatically:
- Generates your digest at your specified time
- Saves it to your history
- (Future) Sends it via email/SMS

**How It Works:**
1. You configure delivery time (e.g., 7:00 AM)
2. System schedules a daily job for that time
3. Every day at 7:00 AM, your digest is generated
4. Digest is saved to your history (accessible via API)

## Understanding the Digest Format

Your digest is organized into clear sections:

### 1. Yesterday's Results
- **Scores:** Final scores for all your teams' games
- **Highlights:** Key moments and standout performances
- **Impact:** How results affect standings or playoff hopes

**Example:**
```
📊 YESTERDAY'S RESULTS

🏀 Lakers 118 - 107 Warriors
   ⭐ LeBron James: 28 pts, 7 reb, 9 ast
   Takeaway: Lakers extend win streak to 5 games

⚽ Manchester United 2 - 1 Liverpool
   ⚽ Bruno Fernandes (45'), Rashford (78')
   Takeaway: United climb to 4th in the table
```

### 2. Today's Schedule
- **Upcoming Games:** All games featuring your teams
- **Game Times:** Converted to your timezone
- **Broadcast Info:** TV channels or streaming services
- **Matchup Preview:** Context and what to watch for

**Example:**
```
📅 TODAY'S SCHEDULE

🏀 Lakers vs. Celtics
   🕐 7:30 PM PT • ESPN
   Preview: Top teams clash. Lakers seeking 6th straight win.
   
⚽ Manchester United vs. Bayern Munich (UCL)
   🕐 12:00 PM PT • Paramount+
   ⚠️ Must-watch: Knockout stage, tied 1-1 on aggregate
```

### 3. Player News
- **Latest News:** Breaking stories about your followed players
- **Injury Updates:** Status reports and return timelines
- **Performance Trends:** Recent form and statistics
- **Transfer News:** Rumors and confirmed moves

**Example:**
```
🗞️ PLAYER NEWS

✅ LeBron James: No injury concerns, questionable tag removed
📰 Bruno Fernandes: Contract extension talks progressing
🏥 Cristiano Ronaldo: Day-to-day with minor knock
```

### 4. Standings (When Relevant)
- **League Tables:** Current positions for your teams
- **Playoff Picture:** Postseason implications
- **Relegation Watch:** If teams are in danger zone

## How Scheduling Works

### Initial Setup

When you save your preferences:
1. System stores your teams, players, leagues
2. Creates a scheduled job for your delivery time
3. Job runs daily at your specified time in your timezone

### What Happens Daily

Every day at your configured time:
1. **Scheduler Triggers:** APScheduler activates your job
2. **Digest Generation:** All 4 AI agents work in parallel
   - Schedule Agent: Finds today's games
   - Scores Agent: Gets yesterday's results
   - Player Agent: Collects latest news
   - Digest Agent: Synthesizes everything
3. **Storage:** Digest is saved to your history
4. **(Future)** Delivery: Email/SMS sent to you

### Persistence

Your scheduled job:
- ✅ Persists across server restarts
- ✅ Handles timezone changes
- ✅ Runs every day automatically
- ✅ Saves history of last 30 digests

## Managing Your Preferences

### Updating Your Preferences

To change your teams, players, or delivery time:

1. **Via Web UI:**
   - Open http://localhost:8000
   - Your current preferences will be pre-filled
   - Modify any fields
   - Click "Save Preferences"
   - System will reschedule your daily digest

2. **Via API:**
```bash
curl -X PUT http://localhost:8000/preferences/YOUR_USER_ID \
  -H "Content-Type: application/json" \
  -d '{
    "teams": ["Lakers", "Celtics"],
    "players": ["LeBron James"],
    "leagues": ["NBA"],
    "delivery_time": "08:00",
    "timezone": "America/New_York"
  }'
```

### Viewing Your Preferences

**Via API:**
```bash
curl http://localhost:8000/preferences/YOUR_USER_ID
```

### Viewing Digest History

Access your last 30 digests:

**Via API:**
```bash
curl http://localhost:8000/digest-history/YOUR_USER_ID?limit=10
```

Returns JSON with digest content and timestamps.

### Deleting Your Account

To remove all your data:

**Via API:**
```bash
curl -X DELETE http://localhost:8000/preferences/YOUR_USER_ID
```

This will:
- Delete your preferences
- Unschedule your daily digest
- Remove your digest history

## Troubleshooting

### Problem: No digest generated

**Possible Causes:**
1. Server not running continuously
2. Scheduling error

**Solutions:**
- Ensure server is running 24/7 for automated digests
- Check server logs for errors
- Try generating digest manually first

### Problem: Game times are wrong

**Possible Causes:**
1. Incorrect timezone setting

**Solutions:**
- Update your timezone in preferences
- Verify timezone matches your location
- Supported timezones listed in dropdown

### Problem: Missing some teams

**Possible Causes:**
1. Team name not recognized
2. Typo in team name

**Solutions:**
- Use commonly recognized names (e.g., "Lakers" not "L.A. Lakers")
- Check for typos in your teams list
- Try variations (e.g., "Man United" or "Manchester United")

### Problem: Digest seems generic

**Possible Causes:**
1. Using LLM fallback (no real sports APIs)
2. Limited team/player information

**Solutions:**
- This is expected for MVP (uses AI to generate realistic content)
- Future versions will integrate real sports APIs
- Add more specific players to follow for better personalization

### Problem: Can't find my user ID

**Solutions:**
- Check browser localStorage: `localStorage.getItem('sport_agent_user_id')`
- User ID is returned when you first save preferences
- Look in browser console after saving preferences

## FAQ

### Q: Is this free to use?

**A:** Yes! The MVP version uses AI to generate sports information with no additional API costs. Future versions may integrate paid sports APIs for real-time data.

### Q: Do I need to create an account?

**A:** No registration required! When you save preferences, you're automatically assigned a user ID stored in your browser.

### Q: Can I follow teams from different sports?

**A:** Absolutely! That's the whole point. Follow NBA, NFL, Premier League, and more all in one digest.

### Q: How many teams can I follow?

**A:** No hard limit, but we recommend 3-7 teams for optimal digest length and readability.

### Q: Will I receive actual real-time scores?

**A:** The MVP uses AI to generate realistic sports content. Future versions will integrate real sports APIs (ESPN, SportsData) for live scores and actual game information.

### Q: Can I get digests multiple times per day?

**A:** Yes! You can generate on-demand digests anytime. Future versions will support multiple scheduled digests per day.

### Q: What if I want to pause my digest?

**A:** You can delete your preferences, which unschedules the daily digest. Save them again when you want to resume.

### Q: How is my data stored?

**A:** Your preferences are stored in a local JSON file on the server. No external databases or third-party storage.

### Q: Can I share my digest with friends?

**A:** Currently, digests are only viewable in your browser or via API. Future versions may add sharing capabilities.

### Q: What sports are supported?

**A:** All major sports! Basketball, Football (Soccer), American Football, Baseball, Hockey, and more. The system works with any sport you specify.

### Q: Can I get digests in other languages?

**A:** Currently English only. Future versions may add multi-language support.

## Getting Help

If you encounter issues not covered here:

1. **Check Server Logs:** Look for error messages in the terminal where the server is running
2. **Test API Endpoints:** Use curl commands to test individual endpoints
3. **Review Configuration:** Verify your preferences are saved correctly
4. **Regenerate Digest:** Try generating a digest manually to test the system

## What's Next?

Planned future enhancements:

- **Real Sports APIs:** Integration with ESPN, SportsData for live scores
- **Email/SMS Delivery:** Receive digests directly in your inbox or phone
- **Mobile App:** Native iOS/Android applications
- **Social Features:** Share digests, compete with friends
- **Fantasy Integration:** Connect with fantasy leagues for player recommendations
- **Advanced Analytics:** Predictions, betting odds, advanced statistics

---

**Version:** 1.0.0 (MVP)  
**Last Updated:** October 19, 2025  
**Need More Help?** Check the README.md for developer documentation

