select *
from vehicle_session_log vsl
where vsl.op_id = ${op_id}
  and vsl.add_at > ${start_time}::timestamp - interval '30 days'
  and vsl.add_at < ${end_at}::timestamp
  and vsl.end_at >= ${start_time}::timestamp
order by vsl.op_id asc, vsl.vhc_id asc, vsl.add_at asc, vsl.end_at asc;

select *
from feeder_vehicle_stat_cap_log fvscl
where fvscl.rule_op_id = 52
  and fvscl.add_at >= ${start_time}::timestamp
  and fvscl.add_at < ${end_time}::timestamp
order by op_id ASC , vhc_id ASC, add_at ASC;

select op_id, vhc_id, mod_at, coalesce(src_at, mod_at) as src_at, cur, inc, dec
from vehicle_stat_cap_log vscl
where vscl.op_id = 52
  and ((
           vscl.mod_at >= '2026-08-13 17:00:00'::timestamp - interval '2 day'
               and vscl.mod_at < '2026-08-14 17:00:00'::timestamp + interval '2 day'
               and vscl.src_at >= '2026-08-13 17:00:00'::timestamp
               and vscl.src_at < '2026-08-14 17:00:00'::timestamp
           )
    OR (
           vscl.mod_at >= '2026-08-13 17:00:00'::timestamp
               and vscl.mod_at < '2026-08-14 17:00:00'::timestamp
               and vscl.src_at is null
           ))
order by op_id ASC , vhc_id ASC, mod_at ASC;