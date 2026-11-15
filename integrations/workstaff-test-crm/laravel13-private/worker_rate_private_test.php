<?php
$base=$argv[1]??'';
if (!$base || !is_file($base.'/PRIVATE_BOT_FIXTURE')) { throw new RuntimeException('Marked synthetic candidate required'); }
require $base.'/vendor/autoload.php';$app=require $base.'/bootstrap/app.php';$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
use Illuminate\Support\Facades\DB;use Illuminate\Support\Facades\Http;use App\Models\Order;
function must($v,$label){if(!$v){throw new RuntimeException('CHECK_FAILED:'.$label);}}
class SyntheticRateActor extends App\Models\User {
 public array $allowed=['read_logist_orders'];
 public function can($abilities,$arguments=[]):bool{return in_array($abilities,$this->allowed,true);}
 public function hasRole($roles,?string $guard=null):bool{return in_array('logist',(array)$roles,true);}
}
must(config('database.connections.mysql.database')==='bot_fixture','private_database');
Http::preventStrayRequests();Http::fake(fn()=>throw new RuntimeException('UNEXPECTED_HTTP'));
$checks=[];$finding=[];DB::beginTransaction();
try{
 $city=DB::table('cities')->insertGetId(['name'=>'Synthetic']);$otherCity=DB::table('cities')->insertGetId(['name'=>'Synthetic other']);
 $branch=DB::table('branches')->insertGetId(['name'=>'Synthetic','timezone'=>'Europe/Moscow','nds'=>0,'city_id'=>$city]);
 $otherBranch=DB::table('branches')->insertGetId(['name'=>'Synthetic other','timezone'=>'Europe/Moscow','nds'=>0,'city_id'=>$otherCity]);
 $customer=DB::table('customers')->insertGetId(['company_name'=>'Synthetic','branch_id'=>$branch]);$contact=DB::table('contact_persons')->insertGetId(['customer_id'=>$customer,'name'=>'Synthetic']);$work=DB::table('work_types')->insertGetId(['name'=>'Synthetic']);
 $id=DB::table('orders')->insertGetId(['order_number'=>'SYNTHETIC-RATE-15','status_id'=>2,'payment_type_id'=>1,'source_id'=>1,'customer_id'=>$customer,'contact_person_id'=>$contact,'branch_id'=>$branch,'work_type_id'=>$work,'logist_id'=>900001,'completion_date'=>'2026-11-15 15:00:00','loader_count'=>2,'duration'=>4,'min_time'=>4,'workers_cost'=>500,'customer_cost'=>900,'city'=>'Synthetic','address'=>'Synthetic address','street'=>'Synthetic street','house'=>'1','coords'=>'[55.0,37.0]','additional'=>'[]','note'=>'Synthetic note','info'=>'']);
 $actor=(new SyntheticRateActor())->forceFill(['id'=>900001,'branch_id'=>$branch,'surname'=>'Synthetic']);$actor->setRelation('roles',collect([(object)['name'=>'logist']]));$actor->setRelation('branch',App\Models\Branch::findOrFail($branch));auth()->setUser($actor);
 $controller=$app->make(App\Http\Controllers\Order\GpmWorkerRateController::class);
 $call=function($payload)use($controller,$actor,$id){$req=Illuminate\Http\Request::create('/synthetic','PATCH',$payload);$req->setUserResolver(fn()=>$actor);return $controller->update($req,$id);};
 $expect=function($label,$status,$fn)use(&$checks){try{$fn();throw new RuntimeException('EXPECTED_REJECTION:'.$label);}catch(Symfony\Component\HttpKernel\Exception\HttpExceptionInterface $e){must($e->getStatusCode()===$status,$label.'_status');}catch(Illuminate\Database\Eloquent\ModelNotFoundException $e){must($status===404,$label.'_not_found');}$checks[]=$label;};
 $res=$call(['workers_cost'=>600,'expected_workers_cost'=>500]);must($res->getData(true)['workers_cost']===600,'success_response');$row=DB::table('orders')->where('id',$id)->first();must((int)$row->workers_cost===600 && (int)$row->customer_cost===900 && $row->address==='Synthetic address','success_data');$checks[]='rate_update_preserves_other_fields';
 $history=Order::findOrFail($id)->histories()->get();must($history->count()===1,'single_history');$props=$history->first()->properties;must((int)$props['Worker hourly rate']['old']===500 && (int)$props['Worker hourly rate']['new']===600,'rate_history_values');$checks[]='rate_history_old_new';
 $call(['workers_cost'=>600,'expected_workers_cost'=>500]);must(Order::findOrFail($id)->histories()->count()===1,'idempotent_no_extra_history');$checks[]='idempotent_retry';
 $expect('stale_rate_rejected',409,fn()=>$call(['workers_cost'=>700,'expected_workers_cost'=>500]));
 $expect('extra_field_rejected',422,fn()=>$call(['workers_cost'=>700,'expected_workers_cost'=>600,'address'=>'changed']));
 $expect('invalid_rate_rejected',422,fn()=>$call(['workers_cost'=>0,'expected_workers_cost'=>600]));
 foreach([3,4,5] as $status){DB::table('orders')->where('id',$id)->update(['status_id'=>$status]);$expect('closed_'.$status.'_rejected',409,fn()=>$call(['workers_cost'=>700,'expected_workers_cost'=>600]));}DB::table('orders')->where('id',$id)->update(['status_id'=>2]);
 DB::table('orders')->where('id',$id)->update(['logist_id'=>900002]);$expect('other_owner_hidden',404,fn()=>$call(['workers_cost'=>700,'expected_workers_cost'=>600]));DB::table('orders')->where('id',$id)->update(['logist_id'=>900001]);
 DB::table('orders')->where('id',$id)->update(['branch_id'=>$otherBranch]);$expect('other_city_hidden',404,fn()=>$call(['workers_cost'=>700,'expected_workers_cost'=>600]));DB::table('orders')->where('id',$id)->update(['branch_id'=>$branch]);
 $actor->allowed=[];$expect('read_permission_required',403,fn()=>$call(['workers_cost'=>700,'expected_workers_cost'=>600]));$actor->allowed=['read_logist_orders'];
 config(['app.url'=>'https://workstaffcrm.ru']);$expect('main_identity_rejected',404,fn()=>$call(['workers_cost'=>700,'expected_workers_cost'=>600]));config(['app.url'=>'https://ts.workstaffcrm.ru']);
 must((int)DB::table('orders')->where('id',$id)->value('workers_cost')===600,'rejections_do_not_change_rate');
 $guard=Order::findOrFail($id);$guard->address='Forbidden synthetic';$denied=false;
 try{$guard->save();}catch(Illuminate\Validation\ValidationException $e){$denied=true;}catch(Symfony\Component\HttpKernel\Exception\HttpExceptionInterface $e){$denied=in_array($e->getStatusCode(),[403,422],true);}
 must($denied && DB::table('orders')->where('id',$id)->value('address')==='Synthetic address','model_address_guard');$checks[]='model_address_guard';
 echo json_encode(['status'=>'PASS','scenarios'=>count($checks),'checks'=>$checks,'real_http_requests'=>0,'real_orders_created'=>0,'production_data_used'=>false,'auth_middleware_exercised'=>false]);
}catch(Throwable $e){echo json_encode(['status'=>'FAILED','checks_completed'=>$checks,'error_class'=>get_class($e),'message'=>$e->getMessage(),'file'=>$e->getFile(),'line'=>$e->getLine()]);$failed=true;}
finally{while(DB::transactionLevel()>0){DB::rollBack();}}
exit(isset($failed)?1:0);
