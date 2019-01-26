import contextlib
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlalchemy.event import listen, listens_for
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
import robostat
from robostat.util import lazy

Base = declarative_base()

class Team(Base):
    __tablename__ = "teams"
    __table_args__ = ( sa.UniqueConstraint("competition_id", "name"), )

    id = sa.Column(sa.Integer, primary_key=True)
    competition_id = sa.Column(sa.Text, nullable=False)
    name = sa.Column(sa.Text, nullable=False)

class Judge(Base):
    __tablename__ = "judges"

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.Text, unique=True, nullable=False)

class Event(Base):
    __tablename__ = "events"
    __table_args__ = ( sa.UniqueConstraint("ts_sched", "arena"), )

    id = sa.Column(sa.Integer, primary_key=True)
    block_id = sa.Column(sa.Text, nullable=False, index=True)
    ts_sched = sa.Column(sa.Integer, nullable=False, index=True)
    arena = sa.Column(sa.Text, nullable=False)

    teams_part = relationship("EventTeam",
            cascade="all, delete-orphan",
            passive_deletes=True,
            back_populates="event",
    )
    team_ids = association_proxy("teams_part", "team_id",
            creator=lambda x: EventTeam(team_id=x))
    teams = association_proxy("teams_part", "team")

    judgings = relationship("EventJudging",
            cascade="all, delete-orphan",
            passive_deletes=True,
            back_populates="event"
    )
    judge_ids = association_proxy("judgings", "judge_id",
            creator=lambda x: EventJudging(judge_id=x))
    judges = association_proxy("judgings", "judge")

    scores = relationship("Score", back_populates="event", viewonly=True)

    def get_block(self, tournament=None):
        if tournament is None:
            tournament = robostat.default_tournament

        return tournament.blocks[self.block_id]

    @property
    def team(self):
        return self.teams[0]

    @property
    def judge(self):
        return self.judges[0]

    @property
    def day_sched(self):
        # XXX this is UTC day lol
        return 24*60*60*(self.ts_sched//(24*60*60))

class EventTeam(Base):
    __tablename__ = "event_teams"
    __table_args__ = ( sa.PrimaryKeyConstraint("event_id", "team_id"), )

    event_id = sa.Column(sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False, index=True)
    team_id = sa.Column(sa.Integer, sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False, index=True)

    event = relationship("Event")
    team = relationship("Team")
    scores = relationship("Score")

class EventJudging(Base):
    __tablename__ = "event_judging"
    __table_args__ = ( sa.PrimaryKeyConstraint("event_id", "judge_id"), )

    event_id = sa.Column(sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False, index=True)
    judge_id = sa.Column(sa.Integer, sa.ForeignKey("judges.id", ondelete="CASCADE"),
            nullable=False, index=True)
    ts = sa.Column(sa.Integer)

    event = relationship("Event")
    judge = relationship("Judge")
    scores = relationship("Score")

    @hybrid_property
    def is_future(self):
        return self.ts == None

class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
            sa.PrimaryKeyConstraint("event_id", "team_id", "judge_id"),
            sa.ForeignKeyConstraint(
                ("event_id", "team_id"),
                ("event_teams.event_id", "event_teams.team_id")
            ),
            sa.ForeignKeyConstraint(
                ("event_id", "judge_id"),
                ("event_judging.event_id", "event_judging.judge_id"),
                ondelete="CASCADE"
            )
    )

    event_id = sa.Column(sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False, index=True)
    team_id = sa.Column(sa.Integer, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    judge_id = sa.Column(sa.Integer, sa.ForeignKey("judges.id", ondelete="CASCADE"),nullable=False)
    data = sa.Column(sa.LargeBinary) # Blob

    event = relationship("Event", viewonly=True)
    team = relationship("Team", viewonly=True)
    judge = relationship("Judge", viewonly=True)

    @hybrid_property
    def has_score(self):
        return self.data != None

listen(Base.metadata, "after_create", sa.DDL("""
    CREATE TRIGGER t_insert_team_scores
    AFTER INSERT ON event_teams
    BEGIN
        INSERT INTO scores(event_id, team_id, judge_id)
        SELECT new.event_id, new.team_id, judge_id
        FROM event_judging
        WHERE event_judging.event_id=new.event_id;
    END;
"""))

listen(Base.metadata, "after_create", sa.DDL("""
    CREATE TRIGGER t_insert_judge_scores
    AFTER INSERT ON event_judging
    BEGIN
        INSERT INTO scores(event_id, team_id, judge_id)
        SELECT new.event_id, team_id, new.judge_id
        FROM event_teams
        WHERE event_teams.event_id=new.event_id;
    END;
"""))

@listens_for(sa.engine.Engine, "connect")
def _sqlite_set_fk(connection, record):
    with contextlib.closing(connection.cursor()) as cursor:
        cursor.execute("PRAGMA foreign_keys=ON;")
