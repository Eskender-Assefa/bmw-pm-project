import argparse
import json
from pathlib import Path
from alembic.config import Config
from alembic import command
from .config import ROOT, DATA_DIR
from .db import SessionLocal
from .ingestion import import_archive, import_files
from .services import seed_requirements
from .schemas import Cohort

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['migrate','import','import-files','openapi','evaluation'])
    parser.add_argument('path',nargs='?')
    parser.add_argument('additional_paths',nargs='*')
    args=parser.parse_args()
    if args.command=='migrate':
        command.upgrade(Config(str(ROOT/'alembic.ini')),'head')
    elif args.command in ('import', 'import-files'):
        if not args.path: parser.error('import requires a source path')
        if args.command == 'import' and args.additional_paths:
            parser.error('import accepts one ZIP path; use import-files for individual sources')
        with SessionLocal() as s:
            result=(import_archive(s,Path(args.path),print) if args.command == 'import'
                    else import_files(s,[args.path, *args.additional_paths],print))
            seed_requirements(s)
            s.commit()
            print(json.dumps(result,indent=2))
    elif args.command=='openapi':
        from .app import app
        (DATA_DIR/'openapi.json').write_text(json.dumps(app.openapi(),indent=2),encoding='utf-8')
    else:
        from .models import EvaluationLabel, Feedback
        from sqlalchemy import select
        with SessionLocal() as s:
            result=[{'feedback_id':l.feedback_id,'split':l.split,'text':s.get(Feedback,l.feedback_id).text,'expected_categories':l.expected_categories} for l in s.scalars(select(EvaluationLabel))]
            (DATA_DIR/'evaluation'/'labeling-set.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
            print(f'Wrote {len(result)} evaluation records.')

if __name__=='__main__': main()
