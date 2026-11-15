"""Chapter 41: the twelve-month rota.  Every small recurring job the earlier chapters created, with an owner, a backup, a cadence or a trigger, the evidence it leaves and what happens when it is late.  No model calls.
  Job        one recurring task: cadence in days (periodic) or an event name (triggered), minutes per run, owner, backup, the artefact it leaves, grace days before it counts as overdue
  Rota       a set of jobs and a head of function (the person things escalate to)
  issues()   what is wrong with the rota itself: UNOWNED, NO_BACKUP, BACKUP_IS_OWNER, NO_EVIDENCE, NO_TRIGGER, NO_CADENCE, OVERLOAD (a person's minutes in a 30-day month over their cap), SINGLE_POINT (a person owns more than `k` jobs with no other person able to cover)
  schedule()  (day, job id) for every periodic run in a window
  load()      minutes per person per 30-day month, from the schedule plus an expected count of triggered runs
  status()    for each job, given the day each last ran: OK, DUE, OVERDUE (past grace; goes to the backup), ESCALATED (past twice the grace; goes to the head), NEVER_RUN
  simulate()  one synthetic year of absences: how many scheduled runs were missed, with and without backups and with and without the overdue alarm
It cannot say a job was done well, only that an artefact with a date exists; it does not know who is really on holiday unless told."""
from __future__ import annotations
import random
from dataclasses import dataclass, field

@dataclass
class Job:
    id: str; name: str; chapter: int; owner: str; backup: str; minutes: int; evidence: str
    cadence: int = 0                # days between runs; 0 means triggered
    trigger: str = ""               # event that starts it when cadence is 0
    per_year: float = 0.0           # expected runs per year of a triggered job
    grace: int = 0                  # days late before OVERDUE
    def periodic(self) -> bool: return self.cadence > 0

@dataclass
class Rota:
    jobs: list[Job] = field(default_factory=list); head: str = ""; cap_minutes: dict = field(default_factory=dict); default_cap: int = 480; single_point_k: int = 6

    def issues(self) -> list[tuple[str, str]]:
        out = []; load = self.load()
        for j in self.jobs:
            if not j.owner: out.append(("UNOWNED", j.id))
            if not j.backup: out.append(("NO_BACKUP", j.id))
            elif j.backup == j.owner: out.append(("BACKUP_IS_OWNER", j.id))
            if not j.evidence: out.append(("NO_EVIDENCE", j.id))
            if j.cadence == 0 and not j.trigger: out.append(("NO_TRIGGER", j.id))
            if j.cadence == 0 and j.trigger and j.per_year <= 0: out.append(("NO_CADENCE", j.id))
        for p, m in sorted(load.items()):
            if m > self.cap_minutes.get(p, self.default_cap): out.append(("OVERLOAD", f"{p}:{m:.0f}min/month"))
        owners = {j.owner for j in self.jobs if j.owner}
        for p in sorted(owners):
            mine = [j for j in self.jobs if j.owner == p]
            alone = [j for j in mine if not j.backup or j.backup == p]
            if len(alone) > self.single_point_k: out.append(("SINGLE_POINT", f"{p}:{len(alone)} jobs without a second person"))
        return out

    def schedule(self, start: int, days: int) -> list[tuple[int, str]]:
        """Periodic jobs are spread so that they do not all fall on day 0: job k of the list starts at offset (k * 7) mod cadence."""
        out = []
        for k, j in enumerate(self.jobs):
            if not j.periodic(): continue
            d = start + (k * 7) % j.cadence
            while d < start + days: out.append((d, j.id)); d += j.cadence
        return sorted(out)

    def load(self) -> dict[str, float]:
        m: dict[str, float] = {}
        for j in self.jobs:
            if not j.owner: continue
            runs = 30 / j.cadence if j.periodic() else j.per_year * 30 / 365
            m[j.owner] = m.get(j.owner, 0.0) + runs * j.minutes
        return m

    def status(self, today: int, last: dict[str, int]) -> dict[str, str]:
        out = {}
        for j in self.jobs:
            if not j.periodic(): continue
            if j.id not in last: out[j.id] = "NEVER_RUN"; continue
            late = today - last[j.id] - j.cadence
            out[j.id] = "OK" if late <= 0 else "DUE" if late <= j.grace else "OVERDUE" if late <= 2 * j.grace + 1 else "ESCALATED"
        return out

def simulate(rota: Rota, seed: int, use_backup: bool, alarm: bool, days: int = 365, absence_rate: float = 0.04, mean_len: int = 8, alarm_check: int = 7) -> dict:
    """Each person is absent on a day with a start probability `absence_rate`/mean_len per day, lasting about `mean_len` days.  A run falls on its scheduled day: it happens if the owner is in; if not and use_backup and the backup is in,
    the backup does it that day; otherwise it is carried by the alarm, which fires on the next `alarm_check` day after the job is overdue and is answered by whoever is in (the backup, then the head); with no alarm it waits for the owner's return.
    A run is MISSED if it is done more than `grace` days after its scheduled day.  Returns counts."""
    r = random.Random(seed); people = {j.owner for j in rota.jobs} | {j.backup for j in rota.jobs} | {rota.head}; people.discard("")
    away = {p: [False] * (days + 60) for p in sorted(people)}
    for p in sorted(people):
        d = 0
        while d < days:
            if r.random() < absence_rate / mean_len:
                n = max(1, int(r.expovariate(1 / mean_len)))
                for k in range(d, min(d + n, days + 59)): away[p][k] = True
                d += n
            d += 1
    runs = missed = late_days = 0
    for day, jid in rota.schedule(0, days):
        j = next(x for x in rota.jobs if x.id == jid); runs += 1
        done = None
        if not away[j.owner][day]: done = day
        elif use_backup and j.backup and not away[j.backup][day]: done = day
        else:
            d = day + 1
            while d < days + 59:
                if not away[j.owner][d]: done = d; break
                if alarm and (d - day) >= j.grace and d % alarm_check == 0:
                    who = [p for p in (j.backup, rota.head) if p and not away[p][d]]
                    if who: done = d; break
                d += 1
            if done is None: done = days + 59
        lag = done - day; late_days += lag
        if lag > j.grace: missed += 1
    return dict(runs=runs, missed=missed, mean_lag=round(late_days / max(runs, 1), 2))


def scorecard(rota: Rota, today: int, last: dict[str, int], backup_last: dict[str, int], evidence: dict[str, tuple[int, int]], waivers: list[tuple[str, int]], alerts: list[tuple[str, int, int | None]],
              library: dict, anchor: dict | None = None) -> dict:
    """The seven first-page numbers of Chapter 41, from records the programme already keeps.  Days are integers on one calendar.
    last          job id -> day of the last run;  backup_last  job id -> day the backup last ran it (absent = never)
    evidence      item id -> (day produced, shelf life in days)
    waivers       (id, review day);  alerts  (id, day raised, day read or None)
    library       dict(last_added=day, families=int, dims_touched=set, dims_all=set);  anchor  dict(step=int, anchor=int) successes on the library, or None"""
    st = rota.status(today, last); over = [j for j, s in st.items() if s in ("OVERDUE", "ESCALATED", "NEVER_RUN")]; esc = [j for j, s in st.items() if s in ("ESCALATED", "NEVER_RUN")]
    jm = {j.id: j for j in rota.jobs}
    worst = max([(today - last.get(j, -10**6) - jm[j].cadence, j) for j in over], default=(0, ""))
    stale = sorted(i for i, (d, shelf) in evidence.items() if today - d > shelf)
    periodic = [j for j in rota.jobs if j.periodic() and j.backup]
    no_backup_run = sorted(j.id for j in periodic if backup_last.get(j.id) is None or today - backup_last[j.id] > 365)
    unread = [(today - d, i) for i, d, r in alerts if r is None]
    past = sorted((today - d, w) for w, d in waivers if d < today)
    return dict(overdue=len(over), escalated=len(esc), most_overdue_days=max(worst[0], 0), most_overdue_job=worst[1],
                evidence_items=len(evidence), evidence_stale=stale,
                backups_never_run=len(no_backup_run), periodic_with_backup=len(periodic), backups_never_run_ids=no_backup_run,
                anchor=anchor, alerts_unread=len(unread), oldest_unread_days=max([a for a, _ in unread], default=0),
                waivers_past_review=len(past), oldest_waiver_past_days=past[-1][0] if past else 0,
                library_age_days=today - library["last_added"], library_families=library["families"], dims_untouched=sorted(set(library["dims_all"]) - set(library["dims_touched"])))
