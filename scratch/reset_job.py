import sqlite3, time

con = sqlite3.connect('data/jobs.sqlite3')
con.execute("UPDATE jobs SET state='queued_render', stage='Queued for retry', error='', updated=? WHERE id='3420f95e48d3'", (time.time(),))
con.commit()
r = con.execute("SELECT id, state, stage FROM jobs WHERE id='3420f95e48d3'").fetchone()
print("Updated job:", r)
