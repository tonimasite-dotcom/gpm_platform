<?php
namespace Illuminate\Database\Migrations {class Migration {}}
namespace Illuminate\Support\Facades {
    class Schema {
        public static $pdo;
        public static function hasColumn($table,$column) {
            $query=self::$pdo->prepare('SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=? AND column_name=?');
            $query->execute([$table,$column]);return (int)$query->fetchColumn()>0;
        }
    }
    class DB {
        public static $pdo;
        public static function statement($sql){return self::$pdo->exec($sql);}
    }
}
namespace {
    use Illuminate\Support\Facades\Schema;
    use Illuminate\Support\Facades\DB;
    function config($key){return 'https://ts.workstaffcrm.ru';}
    $dsn=getenv('GPM_PROFILE_TEST_MYSQL_DSN');
    if (!$dsn || strpos($dsn,'host=127.0.0.1;')===false) {throw new \RuntimeException('Isolated CI database required');}
    $pdo=new \PDO($dsn,'root','synthetic-profile-password',[\PDO::ATTR_ERRMODE=>\PDO::ERRMODE_EXCEPTION]);
    Schema::$pdo=$pdo;DB::$pdo=$pdo;
    $pdo->exec('CREATE TABLE users(id INT PRIMARY KEY,role VARCHAR(20),phone VARCHAR(30),password_hash VARCHAR(100)) ENGINE=InnoDB');
    $insert=$pdo->prepare('INSERT INTO users VALUES (?,?,?,?)');
    foreach([[1,'logist','+70000000001','synthetic-1'],[2,'admin','+70000000002','synthetic-2'],[3,'loader','+70000000003','synthetic-3']] as $row){$insert->execute($row);}
    $before=$pdo->query('SELECT * FROM users ORDER BY id')->fetchAll(\PDO::FETCH_ASSOC);
    $columnsBefore=$pdo->query('SHOW COLUMNS FROM users')->fetchAll(\PDO::FETCH_ASSOC);
    require __DIR__.'/2026_11_22_210000_add_gpm_app_crm_id_to_users.php';
    $migration=new \AddGpmAppCrmIdToUsers;$migration->up();
    $after=$pdo->query('SELECT * FROM users ORDER BY id')->fetchAll(\PDO::FETCH_ASSOC);
    foreach($after as $i=>$row){if($row['gpm_app_crm_id']!==null){throw new \RuntimeException('Non-null default');}unset($row['gpm_app_crm_id']);if($row!==$before[$i]){throw new \RuntimeException('Existing identity changed');}}
    $columnsAfter=$pdo->query('SHOW COLUMNS FROM users')->fetchAll(\PDO::FETCH_ASSOC);
    $added=array_pop($columnsAfter);
    if($columnsAfter!==$columnsBefore || $added['Field']!=='gpm_app_crm_id' || $added['Null']!=='YES' || strpos($added['Type'],'unsigned')===false){throw new \RuntimeException('Unexpected schema change');}
    $pdo->exec('UPDATE users SET gpm_app_crm_id=1 WHERE id=1');
    if((int)$pdo->query('SELECT gpm_app_crm_id FROM users WHERE id=1')->fetchColumn()!==1){throw new \RuntimeException('ID persistence failed');}
    try{$migration->down();throw new \LogicException('Rollback unexpectedly dropped data');}catch(\RuntimeException $error){if($error instanceof \LogicException){throw $error;}}
    if((int)$pdo->query('SELECT gpm_app_crm_id FROM users WHERE id=1')->fetchColumn()!==1){throw new \RuntimeException('Rollback lost ID');}
    echo "MySQL online nullable-column migration PASS: existing users/phones/passwords preserved; saved ID retained on code rollback\n";
}
