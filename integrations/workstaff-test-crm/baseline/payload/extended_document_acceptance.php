<?php
use App\Models\User;
use App\Models\Branch;
use App\Models\Documents\DocumentLink;
use App\Services\Document\GenerateDocumentService;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

$work='/root/gpm-ts-update/20261106-baseline-01';$app=null;$stage='bootstrap';$checks=[];$artifacts=[];$generated=[];
function xdAssert($v): void {if (!$v) throw new RuntimeException('EXTENDED_DOCUMENT_ASSERTION_FAILED');}
function xdCheck($name,$fn): void {global $stage,$checks;$stage=$name;$fn();$checks[]=$name;}
function xdReject($field,$fn): void {
    try {$fn();} catch (Illuminate\Validation\ValidationException $e) {xdAssert(array_key_exists($field,$e->errors()));return;}
    throw new RuntimeException('EXPECTED_DOCUMENT_REJECTION_MISSING');
}
function xdGenerate($label,array $data): array {
    global $fixture,$artifacts,$generated;
    $result=app(GenerateDocumentService::class)->generate($data);
    $parts=isset($result['document'])?[$result]:$result;
    xdAssert(count($parts)>0);
    foreach ($parts as $index=>$part) {
        if ($index===0) xdAssert(isset($part['document']));
        else xdAssert(in_array((int)$data['doc_type'],[DocumentLink::CONTRACT_IP,DocumentLink::CONTRACT_OOO],true));
        foreach (['word','pdf','word_noimg','pdf_noimg'] as $kind) {
            $field=str_starts_with($kind,'word')?'storage_word':'storage_pdf';$relative=$part[$kind][$field]??null;
            xdAssert(is_string($relative) && !str_contains($relative,'..'));
            $path=$fixture.'/storage/app/'.$relative;xdAssert(realpath($path)===$path && is_file($path) && filesize($path)>100);
            if (str_starts_with($kind,'pdf')) xdAssert(file_get_contents($path,false,null,0,5)==='%PDF-');
            else {
                $z=new ZipArchive();xdAssert($z->open($path)===true);$xml=$z->getFromName('word/document.xml');$z->close();
                xdAssert(is_string($xml) && strpos($xml,'${')===false);
                if (in_array((int)$data['doc_type'],[1,2,3],true)) xdAssert(strpos($xml,'PRIVATE SYNTHETIC SERVICE')!==false);
                if ((int)$data['doc_type']===DocumentLink::ACT && is_file($GLOBALS['work'].'/document-template-overlays-20261109/manifest.json')) {
                    $text=html_entity_decode(strip_tags($xml));
                    xdAssert(strpos($text,'В том числе НДС')!==false && strpos($text,'НДС не облагается')===false);
                    $amount=(float)$data['nds']===5.0?'58.79':'205.76';xdAssert(strpos(str_replace(',','.',$text),$amount)!==false);
                }
                if ((int)$data['doc_type']===DocumentLink::CONTRACT_IP && $index===2
                    && is_file($GLOBALS['work'].'/document-template-overlays-20261109/manifest.json')) {
                    $text=html_entity_decode(strip_tags($xml));
                    xdAssert(substr_count($text,$data['doc_number'])>=2 && strpos($text,'033/22')===false && strpos($text,'2022')===false);
                }
            }
            $artifacts[]=['case'=>$label,'part'=>$index,'kind'=>$kind,'path'=>$path,'bytes'=>filesize($path),'sha256'=>hash_file('sha256',$path)];
        }
    }
    $generated[$label]=$result;return $result;
}
try {
    $app=require __DIR__.'/private_runtime_bootstrap.php';
    $fixture=getenv('GPM_TS_DOCUMENT_FIXTURE');
    xdAssert(is_string($fixture) && preg_match('#^'.preg_quote($work,'#').'/extended-document-fixtures-[a-f0-9]{12}$#D',$fixture)
        && realpath($fixture)===$fixture && is_dir($fixture.'/public')
        && getenv('XDG_CONFIG_HOME')===$fixture.'/config' && getenv('TMPDIR')===$fixture.'/tmp');
    $app->instance('path.public',$fixture.'/public');
    config(['filesystems.default'=>'private_extended_documents',
        'filesystems.disks.private_extended_documents'=>['driver'=>'local','root'=>$fixture.'/storage/app']]);
    mkdir($fixture.'/storage/app/public/document_templates',0700,true);
    xdAssert(symlink($fixture.'/storage/app/public',$fixture.'/public/storage'));
    $templates=$work.'/file-recovery-20261109/tree/storage/app/public/document_templates';
    $templateCount=0;
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($templates,FilesystemIterator::SKIP_DOTS)) as $source) {
        if (!$source->isFile() || $source->isLink() || str_starts_with($source->getFilename(),'~$')) continue;
        $relative=substr($source->getPathname(),strlen($templates)+1);$target=$fixture.'/storage/app/public/document_templates/'.$relative;
        if (!is_dir(dirname($target))) mkdir(dirname($target),0700,true);
        xdAssert(realpath($source->getPathname())===$source->getPathname() && copy($source->getPathname(),$target));$templateCount++;
    }
    $overlay=$work.'/document-template-overlays-20261109';$overlayApplied=false;
    if (is_file($overlay.'/manifest.json')) {
        foreach (json_decode(file_get_contents($overlay.'/manifest.json'),true,512,JSON_THROW_ON_ERROR) as $entry) {
            $source=$overlay.'/'.$entry['relative'];$original=$templates.'/'.$entry['relative'];
            xdAssert(realpath($source)===$source && hash_file('sha256',$source)===$entry['overlay_sha256']
                && hash_file('sha256',$original)===$entry['source_sha256']);
            xdAssert(copy($source,$fixture.'/storage/app/public/document_templates/'.$entry['relative']));
        }
        $overlayApplied=true;
    }
    chdir($fixture.'/public');DB::beginTransaction();$tag=bin2hex(random_bytes(6));
    $actorId=DB::table('users')->insertGetId(['surname'=>'Synthetic','first_name'=>'ExtendedDocuments',
        'email'=>'private-extended-doc-'.$tag.'@example.invalid','password'=>Hash::make(bin2hex(random_bytes(20))),
        'branch_id'=>0,'active'=>1,'created_at'=>now(),'updated_at'=>now()]);
    $actor=User::findOrFail($actorId);$actor->assignRole(Spatie\Permission\Models\Role::findByName('head','api'));
    $app['auth']->guard()->setUser($actor);
    $customers=[];$invoices=[];$input=[];$mediaEvidence=[];
    foreach ([1,2] as $org) {
        $customerId=DB::table('customers')->insertGetId(['company_name'=>'PRIVATE DOC CUSTOMER '.$tag.' '.$org,
            'director_fullname'=>'Synthetic Test Director','legal_address'=>'PRIVATE SYNTHETIC ADDRESS',
            'mailing_address'=>'PRIVATE SYNTHETIC ADDRESS','position'=>'Director','INN'=>'0000000000',
            'KPP'=>'000000000','OGRN'=>'0000000000000','BIK'=>'000000000','checking_account'=>'00000000000000000000',
            'correlation_account'=>'00000000000000000000','bank_name'=>'PRIVATE SYNTHETIC BANK',
            'branch_id'=>$org,'created_at'=>now(),'updated_at'=>now()]);$customers[]=$customerId;
        $data=['doc_type'=>DocumentLink::ACCOUNT,'branch_id'=>$org,'customer_id'=>$customerId,'is_img'=>0,
            'date'=>'2026-11-09','doc_number'=>'PRIVATE-'.$tag.'-'.$org,'nds'=>(float)Branch::findOrFail($org)->nds,
            'services'=>[['work_type'=>'PRIVATE SYNTHETIC SERVICE','count'=>2,'unit'=>'час','cost'=>617.28,'total_cost'=>1234.56]]];
        $input[$org]=$data;
        if ($org===1 && $overlayApplied) xdCheck('act_zero_vat_data_remains_exempt',function () use ($data) {
            $noVat=$data;$noVat['doc_type']=DocumentLink::ACT;$noVat['nds']=0;
            $result=app(App\Services\Document\DocumentData\ActDataService::class)->getData($noVat);
            xdAssert($result['vat_summary']==='НДС не облагается.');
        });
        xdCheck('org'.$org.'_invoice_real_generation',function () use ($org,$data,&$invoices) {$invoices[$org]=xdGenerate('org'.$org.'-invoice',$data);});
        xdCheck('org'.$org.'_invoice_code_reserved_once',function () use ($org,&$invoices) {
            xdAssert(DB::table('document_payment_codes')->where('document_id',$invoices[$org]['document']->id)->count()===1);
        });
        foreach ([DocumentLink::ACT,DocumentLink::UPD] as $type) {
            $child=$data;$child['doc_type']=$type;$child['doc_number'].='-'.$type;
            $child['source_document_id']=$invoices[$org]['document']->id;
            $child['services'][0]['source_service_id']=$invoices[$org]['document']->services()->firstOrFail()->id;
            xdCheck('org'.$org.'_type'.$type.'_generation_and_source_links',function () use ($child,$org,$type) {
                $result=xdGenerate('org'.$org.'-type'.$type.'-noimg',$child);$id=$result['document']->id;
                xdAssert(DB::table('document_payment_links')->where('child_document_id',$id)->where('parent_document_id',$child['source_document_id'])->count()===1);
                xdAssert(DB::table('document_payment_line_links')->whereIn('child_service_id',$result['document']->services()->pluck('id'))->count()===1);
                xdAssert(DB::table('document_payment_codes')->where('document_id',$id)->count()===0);
            });
        }
        xdCheck('org'.$org.'_unchanged_invoice_preserves_code_and_files',function () use ($data,$org,&$invoices) {
            $document=$invoices[$org]['document']->fresh();$path=$GLOBALS['fixture'].'/storage/app/'.$document->storage_pdf;
            $hash=hash_file('sha256',$path);$code=DB::table('document_payment_codes')->where('document_id',$document->id)->value('code');
            $result=app(GenerateDocumentService::class)->generate($data+['id'=>$document->id]);
            xdAssert($result['document']->id===$document->id && hash_file('sha256',$path)===$hash);
            xdAssert(DB::table('document_payment_codes')->where('document_id',$document->id)->value('code')===$code);
        });
        xdCheck('org'.$org.'_existing_invoice_vat_change_refused',function () use ($data,$org,&$invoices) {
            $bad=$data;$bad['id']=$invoices[$org]['document']->id;$bad['nds']=(float)$invoices[$org]['document']->nds+1;
            xdReject('nds',function () use ($bad) {app(GenerateDocumentService::class)->generate($bad);});
        });
        xdCheck('org'.$org.'_missing_seal_refused_before_render',function () use ($data) {
            $data['is_img']=1;xdReject('is_img',function () use ($data) {app(GenerateDocumentService::class)->generate($data);});
        });
        // Copy only exact, regular restored TS image files; never follow the live public/storage link.
        $branch=Branch::findOrFail($org);$available=true;$copied=[];
        foreach (['seals','signatures'] as $collection) {
            $m=$branch->getFirstMedia($collection);
            if (!$m) {if ($collection==='seals') $available=false;continue;}
            $filename=(string)$m->file_name;
            if ($filename==='' || basename($filename)!==$filename) {$available=false;continue;}
            $source=$work.'/file-recovery-20261109/tree/storage/app/public/'.$m->id.'/'.$filename;
            if (realpath($source)!==$source || !is_file($source)) {$available=false;continue;}
            $target=$GLOBALS['fixture'].'/storage/app/public/'.$m->id.'/'.$filename;
            if (!is_dir(dirname($target))) mkdir(dirname($target),0700,true);
            xdAssert(copy($source,$target));$copied[]=$collection;
        }
        $mediaEvidence['org'.$org]=['restored_images_available'=>$available,'collections_copied'=>$copied];
        if ($available) foreach ([DocumentLink::ACCOUNT,DocumentLink::ACT,DocumentLink::UPD] as $type) {
            $with=$data;$with['doc_type']=$type;$with['is_img']=1;$with['doc_number'].='-IMG-'.$type;
            xdCheck('org'.$org.'_type'.$type.'_with_restored_images',function () use ($org,$type,$with) {xdGenerate('org'.$org.'-type'.$type.'-img',$with);});
        }
        $contract=$data;$contract['doc_type']=$org===1?DocumentLink::CONTRACT_IP:DocumentLink::CONTRACT_OOO;
        $contract['doc_number'].='-CONTRACT';$contract['is_img']=$available?1:0;
        xdCheck('org'.$org.'_contract_and_three_applications',function () use ($org,$contract) {
            $result=xdGenerate('org'.$org.'-contract',$contract);xdAssert(count($result)===4);
            xdAssert($result[0]['document']->applications()->count()===3);
        });
    }
    xdCheck('cross_customer_source_refused',function () use ($input,$invoices) {
        $bad=$input[1];$bad['doc_type']=DocumentLink::ACT;$bad['customer_id']=$input[2]['customer_id'];
        $bad['source_document_id']=$invoices[1]['document']->id;
        xdReject('customer_id',function () use ($bad) {app(GenerateDocumentService::class)->generate($bad);});
    });
    xdCheck('cross_organization_source_refused',function () use ($input,$invoices) {
        $bad=$input[1];$bad['doc_type']=DocumentLink::UPD;$bad['branch_id']=2;$bad['source_document_id']=$invoices[1]['document']->id;
        xdReject('branch_id',function () use ($bad) {app(GenerateDocumentService::class)->generate($bad);});
    });
    xdCheck('existing_document_type_change_refused',function () use ($input,$invoices) {
        $bad=$input[1];$bad['id']=$invoices[1]['document']->id;$bad['doc_type']=DocumentLink::ACT;
        xdReject('doc_type',function () use ($bad) {app(GenerateDocumentService::class)->generate($bad);});
    });
    file_put_contents($fixture.'/artifact-index-private.json',json_encode($artifacts,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));
    while (DB::transactionLevel()>0) DB::rollBack();
    xdAssert(!DB::table('users')->where('id',$actorId)->exists() && DB::table('customers')->whereIn('id',$customers)->count()===0);
    $report=['success'=>true,'scenarios_passed'=>count($checks),'scenarios'=>$checks,'template_files_restored'=>$templateCount,
        'document_files_verified'=>count($artifacts),'reviewed_template_overlays_applied'=>$overlayApplied,
        'restored_media'=>$mediaEvidence,'all_synthetic_transactions_rolled_back'=>true,
        'real_generators_and_libreoffice_used'=>true,'existing_issuer_read_only'=>true,'external_delivery_used'=>false,
        'private_outputs_contain_ts_requisites'=>true,'visual_acceptance_completed'=>false,'live_crm_changed'=>false,'release_ready'=>false];
    echo json_encode($report).PHP_EOL;
} catch (Throwable $e) {
    if ($app) while (DB::transactionLevel()>0) DB::rollBack();
    if (isset($fixture) && is_dir($fixture)) {
        file_put_contents($fixture.'/private-error.log',(string)$e);
        file_put_contents($fixture.'/artifact-index-private.json',json_encode($artifacts,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));
    }
    $report=['success'=>false,'failed_stage'=>$stage,'scenarios_passed'=>count($checks),'exception_type'=>get_class($e),
        'raw_details_withheld'=>true,'live_crm_changed'=>false];
    if ($e instanceof Illuminate\Validation\ValidationException) $report['validation_fields']=array_keys($e->errors());
    echo json_encode($report).PHP_EOL;exit(1);
}
