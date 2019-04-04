# Blatant

## Released 2019-Mar-08

### Full outline below:


**Bot Changes**

fixed past times in natural

switched message for long times in natural

removed the ability to specify negative times in remind

added `$timer` commands: `timer list/start/delete`

lang and timezone are now stored for both servers (as fallback) and users (as override)

lang, timezone, remind, interval, natural all enabled in DM

reminders all have UIDs of 64 characters for usage in the web

switched out random module for secrets module


**Postman Changes**

combined sql queries

changed the interval switching to replace within the database rather than just `mod`-ing it within the postman


**Database Changes**

new table for timers

changed time from bigint to int

changed position from tinyint to int

reminders all have UIDs


**Web Changes**

removed up/down arrows from interval

added database controlled caching for guilds, channels, roles, members, users

added refresh button to refresh cache

removed guilds, reminders, channels, patreon from session variables

added drop down next to intervals that specifies the time unit

attached javascript that modifies interval value when drop down changed

added ability to assign multiple intervals to a reminder

ability to remove an interval

moved around help entries

added an announcements section containing details on dashboard, promotional opportunities, upvoting

added a card on the dashboard asking for upvotes

added an updates route containing logs of all the updates

added a markdown parser

switched out random module for secrets module

moved API requesting into a separate function