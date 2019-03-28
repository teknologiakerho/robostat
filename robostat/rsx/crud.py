import click
import sqlalchemy as sa
from robostat.rsx.common import RsxError, nameid

add_sym = click.style("[+]", fg="green", bold=True)
del_sym = click.style("[-]", fg="red", bold=True)

# %id = valitse id:n mukaan
# muuten, valitse nimen mukaan
def _split_selectors(selectors):
    ids = []
    names = []

    for s in selectors:
        if s.startswith("%"):
            ids.append(int(s[1:]))
        else:
            names.append(s)

    return ids, names

# cls = Team tai Judge
def query_named(db, cls, ids=None, names=None):
    return db.query(cls)\
            .filter(sa.or_(
                cls.id.in_(ids) if ids else False,
                cls.name.in_(names) if names else False
            ))

def query_selectors(db, cls, selectors):
    ids, names = _split_selectors(selectors)
    return query_named(db, cls, ids=ids, names=names)

def insert_missing_interactive(db, cls, selectors, creator=None, autoconfirm=None, echo=True):
    ids, names = _split_selectors(selectors)
    have_ids = db.query(cls).filter(cls.id.in_(ids)).all()

    if len(have_ids) < len(ids):
        raise RsxError("Missing ids: %s (from class: %s)" % (
            set(ids).difference(x.id for x in have_ids),
            cls.__name__
        ))

    have_names = db.query(cls).filter(cls.name.in_(names)).all()

    if len(have_names) < len(names):
        missing = set(names).difference(x.name for x in have_names)

        if autoconfirm is False or creator is None:
            raise RsxError("Missing names: %s (from class: %s)" % (missing, cls.__name__))

        if not autoconfirm:
            click.echo("Not in db (%d): %s" % (len(missing), ", ".join(missing)))
            click.confirm("OK to add?", default=True, abort=True)

        add = list(map(creator, missing))

        db.add_all(add)

        # commit että tietokanta antaa niille primary keyt
        db.commit()

        if echo:
            for x in add:
                click.echo("%s %s" % (add_sym, nameid(x)))

        have_names += add

    return have_ids + have_names
