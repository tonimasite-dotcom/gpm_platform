<?php
require __DIR__ . '/GpmWorkerMatchPolicy.php';
use App\Services\Gpm\GpmWorkerMatchPolicy as Policy;

$now = strtotime('2026-11-23T10:00:00Z');
$id = '11111111-1111-4111-8111-111111111111';
$other = '22222222-2222-4222-8222-222222222222';
$profile = [
 'account_id'=>$id, 'role'=>'worker', 'active'=>true, 'phone'=>'+7 (900) 000-00-01',
 'phone_country'=>'RU', 'surname'=>'Fixture', 'first_name'=>'Worker', 'branch_id'=>1,
 'phone_verification'=>['method'=>'sms','environment'=>'production','phone'=>'+79000000001',
 'verified_at'=>'2026-11-23T09:55:00Z','proof_id'=>str_repeat('p',32)],
];
$person = ['id'=>'101','phone'=>'8 (900) 000-00-01','roles'=>['loader'],'active'=>true,'deleted'=>false];
$checks = 0;
function check($condition, $message) {
 global $checks;
 if (!$condition) throw new RuntimeException($message);
 $checks++;
}
function resolve($p, $c, $l=null, $owners=null) {
 global $id,$now;
 return Policy::resolve($p,$c,$l,$owners ?? [$id],$now);
}
function action($p,$c,$expected,$link=null,$owners=null) {
 check(resolve($p,$c,$link,$owners)['action']===$expected,$expected);
}
check(Policy::phone('8 (900) 000-00-01')==='+79000000001','RU trunk');
check(Policy::phone('9000000001')==='+79000000001','RU local');
check(Policy::phone('+1 900 000 0001','INT')==='+19000000001','international retained');
foreach (['900','+79000000001 ext 1','+790000000011','++79000000001'] as $bad) {
 check(Policy::phone($bad)===null,'invalid format rejected');
}
action($profile,[$person],'link_existing');
check(resolve($profile,[$person])['crm_worker_id']==='101','existing identity');
action($profile,[],'create_worker');
action($profile,[$person,$person],'review');
action($profile,[$person], 'review', null, [$id,$other]);
$bad=$profile;unset($bad['phone_verification']);action($bad,[$person],'wait');
$bad=$profile;$bad['phone_verification']['environment']='preview';action($bad,[$person],'wait');
$bad=$profile;$bad['phone_verification']['method']='test';action($bad,[$person],'wait');
$bad=$profile;$bad['phone_verification']['verified_at']='2000-01-01T00:00:00Z';action($bad,[$person],'wait');
$bad=$profile;$bad['phone_verification']['verified_at']='2027-01-01T00:00:00Z';action($bad,[$person],'wait');
$bad=$profile;$bad['phone']='+79000000002';action($bad,[$person],'wait');
$bad=$profile;$bad['active']=false;action($bad,[$person],'skip');
$bad=$profile;$bad['role']='logist';action($bad,[$person],'review');
$bad=$person;$bad['roles']=['admin'];action($profile,[$bad],'review');
$bad=$person;$bad['roles']=['loader','admin'];action($profile,[$bad],'review');
$bad=$person;$bad['deleted']=true;action($profile,[$bad],'review');
$bad=$person;$bad['app_account_id']=$other;action($profile,[$bad],'review');
$inactive=$person;$inactive['active']=false;action($profile,[$inactive],'link_existing');
check($inactive['active']===false,'status untouched');
$before=$person;resolve($profile,[$person]);check($before===$person,'CRM data untouched');
$bad=$profile;unset($bad['surname']);action($bad,[],'wait');
$bad=$profile;unset($bad['branch_id']);action($bad,[],'wait');
$intl=$profile;$intl['phone']='+19000000001';$intl['phone_country']='INT';
$intl['phone_verification']['phone']=$intl['phone'];action($intl,[$person],'create_worker');
$changed=$profile;$changed['phone']='+79000000099';unset($changed['phone_verification']);
action($changed,[$person],'keep_link',['account_id'=>$id,'crm_worker_id'=>'101']);
action($changed,[],'review',['account_id'=>$id,'crm_worker_id'=>'101']);
$office=$person;$office['phone']=null;$office['work_phone']=$profile['phone'];
action($profile,[$office],'create_worker');
echo "Worker matching policy: {$checks} checks passed\n";
