SELECT boathouse
FROM manual_overrides
WHERE current_timestamp BETWEEN start_time AND end_time
