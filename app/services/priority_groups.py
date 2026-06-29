from app.db import models

async def get_priority_group(implementer_id):
        implementer_pg = await models.Implementer.get_or_none(id=implementer_id)
        if implementer_pg.employment_type == 'state':
            return 1
        if implementer_pg.nationality and implementer_pg.passport and implementer_pg.inn:
            return 2  
        elif implementer_pg.nationality and implementer_pg.inn:
            return 3 
        elif implementer_pg.inn and implementer_pg.passport:
            return 4 
        elif implementer_pg.inn:
            return 5  
        elif implementer_pg.nationality and implementer_pg.passport:
            return 6 
        elif implementer_pg.passport:
            return 7
        elif implementer_pg.nationality:
            return 8  
        else:
            return 0  
  