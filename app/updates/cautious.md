# Cautious

## Released 2019-Apr-07

### Full outline below:


**Bot Changes**

new command `nudge` to set up custom offsets

refactored `remind` and `natural`

changed a dictionary to a list

moved get strings method to a method of the language ORM object

fixed up caching to hopefully be less resource consuming

moved config to a separate object

renamed some strings to be more in line with other string names

renamed patreon function

changed how times in the past are dealt with

languages now loaded entirely from DB (no file check required)


**Database Changes**

renamed hashpack column to UID

added an 'enabled' column to reminders

new tables: channel nudge and languages


**Postman Changes**

cleaned up some queries

removed thread joining

shortened timeout to 5 seconds (from 30)


**Web Changes**

fix to deleting intervals