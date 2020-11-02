from typing import Set

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import TIMESTAMP
from sqlalchemy import VARCHAR

from ..admin import AdminModelView
from .database import Base
from .database import execute_sql_from_file


class ManualOverrides(Base):
    __tablename__ = 'manual_overrides'
    boathouse = Column(VARCHAR(255), primary_key=True)
    start_time = Column(TIMESTAMP, primary_key=True)
    end_time = Column(TIMESTAMP, primary_key=True)
    reason = Column(VARCHAR(255))


class ManualOverridesModelView(AdminModelView):
    form_choices = {
        'reason': [
            ('cyanobacteria', 'Cyanobacteria'),
            ('sewage', 'Sewage'),
            ('other', 'Other'),
        ],
        'boathouse': [
            ('Newton Yacht Club', 'Newton Yacht Club'),
            ('Watertown Yacht Club', 'Watertown Yacht Club'),
            ('Community Rowing, Inc.', 'Community Rowing, Inc.'),
            ('Northeastern''s Henderson Boathouse', 'Northeastern''s Henderson Boathouse'),
            ('Paddle Boston at Herter Park', 'Paddle Boston at Herter Park'),
            ('Harvard''s Weld Boathouse', 'Harvard''s Weld Boathouse'),
            ('Riverside Boat Club', 'Riverside Boat Club'),
            ('Charles River Yacht Club', 'Charles River Yacht Club'),
            ('Union Boat Club', 'Union Boat Club'),
            ('Community Boating', 'Community Boating'),
            ('Paddle Boston at Kendall Square', 'Paddle Boston at Kendall Square')
        ]
    }

    def __init__(self, session):
        super().__init__(ManualOverrides, session)


def get_currently_overridden_boathouses() -> Set[int]:
    return set(
        execute_sql_from_file(
            'currently_overridden_boathouses.sql'
        )["boathouse"].unique()
    )
