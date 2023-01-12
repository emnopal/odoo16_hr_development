-- used
create or replace view hr_used_day_off as (
	select
		used.name,
		sum(case when used.day_off_type ~* '(?<!\w)(?:annual)(?!\w)' then used.used_days end) as annual_leave,
		sum(case when used.day_off_type ~* '(?<!\w)(?:replacement)(?!\w)' then used.used_days end) as replacement_day_off,
		sum(case when used.day_off_type ~* '(?<!\w)(?:sick)(?!\w)' then used.used_days end) as sick,
		sum(case when used.day_off_type ~* '(?<!\w)(?:unpaid)(?!\w)' then used.used_days end) as unpaid_leave
	from (
	select
		e.name,
		sum(abs(r.number_of_days)) used_days,
		(t.name -> 'en_US')::text as day_off_type
	from hr_leave_report r
	join hr_employee e
	on e.id = r.employee_id
	join hr_leave_type t
	on t.id = r.holiday_status_id
	where r.state = 'validate' and r.leave_type = 'request'
	group by e.name, r.number_of_days, day_off_type) used
	group by used.name
);

select * from hr_used_day_off;

-- balance
create or replace view hr_balance_day_off as (
	select
		balance.name,
		sum(case when balance.day_off_type ~* '(?<!\w)(?:annual)(?!\w)' then balance.balance_days end) as annual_leave,
		sum(case when balance.day_off_type ~* '(?<!\w)(?:replacement)(?!\w)' then balance.balance_days end) as replacement_day_off,
		sum(case when balance.day_off_type ~* '(?<!\w)(?:sick)(?!\w)' then balance.balance_days end) as sick,
		sum(case when balance.day_off_type ~* '(?<!\w)(?:unpaid)(?!\w)' then balance.balance_days end) as unpaid_leave
	from (
		select
			e.name,
			sum(r.number_of_days) balance_days,
			(t.name -> 'en_US')::text as day_off_type
		from hr_leave_report r
		join hr_employee e
		on e.id = r.employee_id
		join hr_leave_type t
		on t.id = r.holiday_status_id
		where r.state = 'validate'
		group by r.holiday_status_id, e.name, t.name
	) balance
	group by balance.name
);

select * from hr_balance_day_off;
