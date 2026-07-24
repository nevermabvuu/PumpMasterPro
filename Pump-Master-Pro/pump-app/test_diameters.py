import sqlite3
import json
conn = sqlite3.connect('pumps.db')
row = conn.execute('SELECT curve_labels, curve_diameters, impeller_dia_mm FROM pumps WHERE id=9').fetchone()
print("Labels:", row[0])
print("Diameters:", row[1])
print("Impeller:", row[2])
