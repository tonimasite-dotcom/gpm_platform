#!/usr/bin/env python3
"""Read-only TS/saved-source audit. No Laravel bootstrap, SQL or external calls."""
from pathlib import Path
import hashlib,json,os,re,subprocess,pwd
TS=Path('/var/www/gruzpiter/data/www/ts.workstaffcrm.ru')
W=Path('/root/gpm-ts-update/20261106-baseline-01')
OUTPUT=Path('/root/gpm-ts-update/minimum-scope-audit-20261110.json')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def env_metadata():
 values={}
 for line in (TS/'.env').read_text().splitlines():
  m=re.match(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$',line)
  if m:values[m.group(1)]=m.group(2).strip('"\'')
 assert values.get('APP_URL','').rstrip('/')=='https://ts.workstaffcrm.ru'
 allowed=['APP_ENV','APP_URL','MAIL_MAILER','MAIL_DRIVER','QUEUE_CONNECTION','CACHE_DRIVER','SESSION_DRIVER',
  'LOGIN_EMAIL_CODE_ENABLED','GPM_APP_ORDER_SYNC_ENABLED']
 return {k:values.get(k,'ABSENT') for k in allowed}
def kernel(root):
 p=root/'app/Console/Kernel.php'
 code='$s=file_get_contents($argv[1]);foreach(token_get_all($s) as $t){if(is_array($t)){if(!in_array($t[0],[T_COMMENT,T_DOC_COMMENT]))echo $t[1];}else echo $t;}'
 result=subprocess.run(['php','-r',code,str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 if result.returncode:raise RuntimeError('STATIC_TOKENIZER_FAILED_DETAILS_WITHHELD')
 text=result.stdout
 names=[m.group(2).split()[0] for m in re.finditer(r'\$schedule->command\s*\(\s*([\'\"])(.*?)\1',text,re.S)]
 if 'documents:reconcile-payments' in text:names.append('documents:reconcile-payments')
 return {'sha256':digest(p),'uncommented_schedule_command_names':names,
  'uncommented_debit_notify_present':'debit:notify' in names,'scheduler_executed':False}
def main():
 os.umask(0o077)
 assert TS.resolve()==TS and (TS/'.env').resolve()==TS/'.env' and not OUTPUT.exists()
 r={'audit_date_moscow':'2026-11-10','read_only_application_audit':True,'ts_safe_environment_flags':env_metadata(),
  'kernels':{label:kernel(root) for label,root in [('live_ts',TS),('saved_ts',W/'source-ts'),('saved_main',W/'source-main'),('candidate',W/'candidate')]},
  'main_reference_is_saved_snapshot':True,'live_main_accessed':False,'laravel_bootstrapped':False,'database_connected':False,
  'scheduled_jobs_or_sync_executed':False,'live_files_changed':False,'external_messages_sent':False,
  'permanent_daily_mail_denial_verified':False,'external_demo_mode_verified':False,'release_ready':False}
 rows=[]
 for p in [Path('/etc/crontab')]+list(Path('/etc/cron.d').glob('*'))+list(Path('/var/spool/cron/crontabs').glob('*')):
  if not p.is_file() or p.is_symlink():continue
  for i,line in enumerate(p.read_text(errors='replace').splitlines(),1):
   if not line.strip() or line.lstrip().startswith('#'):continue
   if str(TS) not in line and not any(v in line for v in ['schedule:run','schedule:work']):continue
   paths=re.findall(r'/(?:[\w.\-]+/)*[\w.\-]+',line)
   rows.append({'file':str(p),'line':i,'mentions_ts':str(TS) in line,'schedule_fields':line.split()[:5],
    'artisan_commands':re.findall(r'artisan\s+([a-zA-Z0-9:_-]+)',line),'absolute_paths':[x for x in paths if not x.startswith('/dev/')]})
 r['inspected_cron_entries']=rows
 r['scheduler_alternative_paths']=[{'path':str(p),'exists':p.exists(),'same_directory_as_ts':p.exists() and p.samefile(TS)}
  for p in [Path('/www/test.workstaffcrm.ru'),Path('/var/www/gruzpiter/data/www/test.workstaffcrm.ru')]]
 selected=['app/Services/WebKlexMailClient.php','app/Services/Mails/MailService.php','app/Services/Mail/MailService.php',
  'app/Services/Banking/BankingService.php','app/Traits/sendSmsTrait.php',
  'app/Services/Order/GpmAppOrderSync.php','app/Services/Order/GpmAppOrderPublisher.php',
  'app/Services/Order/GpmLogistOrderGuard.php','app/Services/Order/GpmWorkerRateRules.php',
  'app/Http/Controllers/Order/GpmWorkerRateController.php','app/Services/Order/CompletedOrderFinancialGuard.php',
  'app/Services/Order/CompletedOrderStaffGuard.php','app/Services/Order/LogistEditAccess.php','app/Models/Order.php']
 r['source_files']={}
 for label,root in [('live_ts',TS),('saved_main',W/'source-main'),('candidate',W/'candidate')]:
  r['source_files'][label]=[]
  for name in selected:
   p=root/name
   if not p.is_file():continue
   text=p.read_text(errors='replace')
   r['source_files'][label].append({'file':name,'sha256':digest(p),
    'imports':re.findall(r'^use (App\\[^;]+);',text,re.M),
    'env_names':sorted(set(re.findall(r'env\(\s*[\'\"]([^\'\"]+)',text)))})
 with OUTPUT.open('x') as out:out.write(json.dumps(r,indent=2)+'\n')
 print(json.dumps({'success':True,'report':str(OUTPUT),'live_ts_smtp_configured':r['ts_safe_environment_flags'].get('MAIL_MAILER')=='smtp',
  'wide_candidate_debit_notify_present':r['kernels']['candidate']['uncommented_debit_notify_present'],
  'permanent_daily_mail_denial_verified':False,'live_files_changed':False}))
if __name__=='__main__':main()
