<?php
require __DIR__.'/GpmWorkerMatchPolicy.php';
require __DIR__.'/GpmPreviewWorkerPolicy.php';
use App\Services\Gpm\GpmPreviewWorkerPolicy as Preview;
use App\Services\Gpm\GpmWorkerMatchPolicy as Production;

$profile = ['profile_id'=>'preview_'.str_repeat('a',32),'environment'=>'registration-preview',
 'verification_method'=>'test_code','phone_verified'=>true,'phone_country'=>'RU',
 'phone'=>'+79000000001','revision'=>str_repeat('f',64),'surname'=>'Пример','first_name'=>'Тест',
 'middle_name'=>'','birth_date'=>'1990-01-01','cities'=>['Москва'],'created_at'=>time()];
$person = ['id'=>'10','phone'=>'8(900)0000001','roles'=>['loader'],'deleted'=>false,'active'=>true];
$count=0;
function check($value) { global $count; if (!$value) throw new RuntimeException('Preview assertion failed'); $count++; }
function result($p,$people,$link=null,$branch=2) {
 return Preview::resolve($p,$people,$link,$branch,true,Preview::INSTANCE);
}
check(result($profile,[$person])['action']==='link');
check(result($profile,[])['action']==='create');
check(result($profile,[],null,null)['reason']==='trusted_branch_required');
check(result($profile,[$person,$person])['reason']==='duplicate_crm_phone');
$bad=$person;$bad['roles']=['admin'];check(result($profile,[$bad])['reason']==='staff_role_collision');
$bad=$person;$bad['roles']=['loader','admin'];check(result($profile,[$bad])['reason']==='staff_role_collision');
$bad=$person;$bad['deleted']=true;check(result($profile,[$bad])['reason']==='deleted_crm_card');
$inactive=$person;$inactive['active']=false;check(result($profile,[$inactive])['action']==='link');
check($inactive['active']===false);
$bad=$person;$bad['preview_profile_id']='preview_'.str_repeat('b',32);
check(result($profile,[$bad])['reason']==='crm_card_already_linked');
$changed=$profile;$changed['phone']='+79000000002';
check(result($changed,[$person],['crm_worker_id'=>'10'])['reason']==='stable_identity');
$bad=$profile;$bad['profile_id']='production-account';check(!Preview::valid($bad));
$bad=$profile;$bad['environment']='production';check(!Preview::valid($bad));
$bad=$profile;$bad['phone_verified']=false;check(!Preview::valid($bad));
$bad=$profile;$bad['first_name']='<script>';check(!Preview::valid($bad));
$intl=$profile;$intl['phone']='+19000000001';$intl['phone_country']='INT';
check(result($intl,[$person])['action']==='create');
$before=$person;result($profile,[$person]);check($before===$person);
foreach ([[false,Preview::INSTANCE],[true,'https://crm.invalid']] as $context) {
 try { Preview::resolve($profile,[$person],null,2,$context[0],$context[1]); throw new RuntimeException('Scope bypass'); }
 catch (DomainException $expected) { check(true); }
}
$snapshot=['protocol'=>Preview::PROTOCOL,'source_instance'=>Preview::INSTANCE,
 'environment'=>'registration-preview','profiles'=>[$profile]];
check(count(Preview::snapshot($snapshot))===1);
$bad=$snapshot;$bad['profiles'][]=$profile;
try { Preview::snapshot($bad); throw new RuntimeException('Duplicate accepted'); }
catch (RuntimeException $expected) { check($expected->getMessage()==='Invalid test worker profile'); }
// A laboratory confirmation never qualifies as production ownership evidence.
$real=['phone'=>$profile['phone'],'phone_country'=>'RU','phone_verification'=>[
 'method'=>'test_code','environment'=>'registration-preview','phone'=>$profile['phone'],
 'verified_at'=>gmdate('c'),'proof_id'=>str_repeat('p',32)]];
check(Production::verifiedPhone($real,time())===null);
echo "Preview worker policy: {$count} checks passed\n";
