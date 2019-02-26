# Acrobatic

## Released 2019-Feb-08

### Here's the full outline of the update

**Database Changes**

- Intervals now stored in a joined table, not in the reminder field

- Better default values for reminder fields and server fields

- Roles separated from the server table

- Blacklists separated from the server table

- todos moved from a JSON file to a table

- More representative types used


**Bot Changes**

- `$del` fixed in DMs

- Removed useless imports

- Natural now has the same time constraints as the normal reminder command

- 150 character limit removed from all reminder commands


**Web Changes**

- Table removed in favor of a new 'card' look

- Cards allow better editing of reminders

- 2 routes: one to GET the dashboard, one to POST an update to a reminder

- 150 character limit removed from reminder adding via the dashboard