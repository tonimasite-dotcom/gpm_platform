# Prepare the reviewed TS profile-ID patch privately; never deploy or run migrations.
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

EXPECTED = {
    'app/Models/User.php': '652293a9600c8ab64f197a2ca40c54db85369a026aa9d85dbd2cbb08c5b6ebea',
    'app/Http/Resources/User.php': '4f1358f87bc813cdff39adf7841a7d01f4c5ccd9762b7dd355a1bad1635051de',
    'app/Http/Requests/User/UserStoreRequest.php': 'f178723792dd59ec63f967cc154bc50f148d0cea079ce853431b30f3346e4a16',
    'app/Services/UserService.php': 'd7e8fcabf06725d07afd2c0465bc01ef7e9fb36f1646fba676f452a0fe985da6',
    'app/Http/Controllers/Settings/ProfileController.php': '45055d62d5b20754a7293dbb9072e87a7097ad6c37c53fca7d89cf9b550e1098',
    'resources/js/pages/app/profile/profile.vue': 'cbc5387e03a1535a944270dfbbcbd736b782b89dca6c12b6a6d3de9ccddd8d49',
    'resources/js/pages/app/users/UserForm.vue': '0e4ce43a4b98b0f74d67ecfa34ab5ea552136019783fb494062054b6e031b5a6',
    'resources/js/pages/app/orders/logist_orders/index.vue': '07e8bee2e0a8b7a585c3401b269fdd16348f51f725db8f9d9972fd61ae8a46a5',
}
MIGRATION = 'database/migrations/2026_11_22_210000_add_gpm_app_crm_id_to_users.php'
HELPER = 'app/Services/Order/GpmAppProfileId.php'


def once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError('Reviewed source anchor changed')
    return text.replace(before, after, 1)


def transform(files, bundle):
    result = dict(files)
    key = 'app/Models/User.php'
    result[key] = once(result[key], "        'work_phone',\n", "        'work_phone',\n        'gpm_app_crm_id',\n")
    result[key] = once(result[key], "        'email_verified_at' => 'datetime',", "        'email_verified_at' => 'datetime',\n        'gpm_app_crm_id' => 'integer',")
    result[key] = once(result[key], "['email', 'phone', 'active', 'uis_id', 'uis_number', 'megafon_id']", "['email', 'phone', 'active', 'uis_id', 'uis_number', 'megafon_id', 'gpm_app_crm_id']")
    key = 'app/Http/Resources/User.php'
    marker = "            'email'             => $this->email,"
    result[key] = once(result[key], marker, marker + "\n            'gpm_app_crm_id'    => $this->hasAnyRole(['logist', 'admin']) && $this->gpm_app_crm_id ? '#'.(int) $this->gpm_app_crm_id : null,")
    key = 'app/Http/Requests/User/UserStoreRequest.php'
    result[key] = once(result[key], "            'work_phone'      => 'nullable|phone:ru',", "            'work_phone'      => 'nullable|phone:ru',\n            'gpm_app_crm_id'   => 'nullable',")
    key = 'app/Services/UserService.php'
    result[key] = once(result[key], 'namespace App\\Services;', 'namespace App\\Services;\n\nuse App\\Services\\Order\\GpmAppProfileId;')
    result[key] = once(result[key], '    public function store(array $data)\n    {', "    public function store(array $data)\n    {\n        $data = GpmAppProfileId::prepare($data, $data['role'] ?? '', null, Auth::user(), null, true);")
    result[key] = once(result[key], '    public function update(User $user, array $data)\n    {', "    public function update(User $user, array $data)\n    {\n        $data = GpmAppProfileId::prepare($data, $data['role'] ?? '', $user->gpm_app_crm_id, Auth::user(), $user);")
    key = 'app/Http/Controllers/Settings/ProfileController.php'
    result[key] = once(result[key], 'use App\\Http\\Controllers\\Controller;', 'use App\\Http\\Controllers\\Controller;\nuse App\\Services\\Order\\GpmAppProfileId;')
    result[key] = once(result[key], "        return tap($user)->update($request->only('phone', 'email'));", "        $data = GpmAppProfileId::prepare(\n            $request->only('phone', 'email', 'gpm_app_crm_id'),\n            $user->hasAnyRole(['logist', 'admin']) ? 'logist' : '',\n            $user->gpm_app_crm_id, $user, $user\n        );\n        return tap($user)->update($data);")
    field = '''        <v-text-field
          v-if="canUseGpmId"
          v-model="form.gpm_app_crm_id"
          label="ID РІ РїСЂРёР»РѕР¶РµРЅРёРё"
          placeholder="#1"
          hint="РЎРєРѕРїРёСЂСѓР№С‚Рµ СЃРІРѕР№ ID РёР· РїСЂРѕС„РёР»СЏ РІ РїСЂРёР»РѕР¶РµРЅРёРё GPM"
          persistent-hint
          maxlength="10"
          prepend-icon="mdi-cellphone-link"
          :error-messages="form.errors.get('gpm_app_crm_id')"
          clearable
        />

'''
    key = 'resources/js/pages/app/profile/profile.vue'
    result[key] = once(result[key], '        <v-btn type="submit"', field + '        <v-btn type="submit"')
    result[key] = once(result[key], "      email: ''", "      email: '',\n      gpm_app_crm_id: ''")
    result[key] = once(result[key], "  computed: mapGetters({\n    user: 'auth/user'\n  }),", "  computed: Object.assign(mapGetters({ user: 'auth/user' }), {\n    canUseGpmId () {\n      return this.$store.getters['auth/role']('logist', 'admin')\n    }\n  }),")
    key = 'resources/js/pages/app/users/UserForm.vue'
    field = '''            <v-text-field
              v-if="gpmAppIdAllowed"
              v-model="form.gpm_app_crm_id"
              label="ID РІ РїСЂРёР»РѕР¶РµРЅРёРё"
              placeholder="#1"
              hint="РЎРєРѕРїРёСЂСѓР№С‚Рµ ID РёР· РїСЂРѕС„РёР»СЏ СЃРѕС‚СЂСѓРґРЅРёРєР° РІ РїСЂРёР»РѕР¶РµРЅРёРё GPM"
              persistent-hint
              maxlength="10"
              prepend-icon="mdi-cellphone-link"
              :error-messages="form.errors.get('gpm_app_crm_id')"
              clearable
            />
'''
    result[key] = once(result[key], '            <v-text-field\n              v-model="form.megafon_id"', field + '            <v-text-field\n              v-model="form.megafon_id"')
    result[key] = once(result[key], "        email: '',", "        email: '',\n        gpm_app_crm_id: '',")
    result[key] = once(result[key], '  computed: {\n    title:', "  computed: {\n    gpmAppIdAllowed () {\n      return ['logist', 'admin'].includes(this.form.role)\n    },\n    title:")
    result[key] = once(result[key], "  watch: {\n    'form.fact_address':", "  watch: {\n    'form.role': function (newVal) {\n      if (!['logist', 'admin'].includes(newVal)) this.form.gpm_app_crm_id = ''\n    },\n    'form.fact_address':")
    result[key] = once(result[key], "        await this.$toast.success(this.$t('saved'))", "        const current = this.$store.getters['auth/user']\n        if (this.modelId && current && String(current.id) === String(this.modelId)) {\n          await this.$store.dispatch('auth/fetchUser')\n        }\n        await this.$toast.success(this.$t('saved'))")
    key = 'resources/js/pages/app/orders/logist_orders/index.vue'
    result[key] = once(result[key], '    openGpmAppModal(item) {\n      this.currentItem = item;', "    openGpmAppModal(item) {\n      const profile = this.$store.getters['auth/user'];\n      this.gpmAppCrmId = profile && profile.gpm_app_crm_id ? String(profile.gpm_app_crm_id) : '';\n      this.gpmAppRecipientMode = 'id';\n      this.currentItem = item;")
    result[HELPER] = (bundle / 'GpmAppProfileId.php').read_text()
    result[MIGRATION] = (bundle / Path(MIGRATION).name).read_text()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root, args.output
    if not root.is_absolute() or root.resolve() != root or root.name != 'ts.workstaffcrm.ru':
        raise RuntimeError('Unexpected TS source scope')
    if not output.is_absolute() or output.resolve() != output or output.exists() or root in output.parents or str(output).startswith('/var/www/'):
        raise RuntimeError('Output must be a new private directory outside hosting')
    php = "require $argv[1].'/vendor/autoload.php'; $v=Dotenv\\Dotenv::createArrayBacked($argv[1])->load(); echo $v['APP_URL']??'';"
    scope = subprocess.run(['/usr/bin/php', '-r', php, str(root)], capture_output=True, text=True, check=True).stdout.rstrip('/')
    if scope != 'https://ts.workstaffcrm.ru':
        raise RuntimeError('TS application URL mismatch')
    files = {}
    for relative, expected in EXPECTED.items():
        path = root / relative
        if path.is_symlink() or root not in path.resolve().parents:
            raise RuntimeError('Unsafe source path')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError('Reviewed TS source changed')
        files[relative] = raw.decode('utf-8')
    for relative in [HELPER, MIGRATION]:
        if (root / relative).exists():
            raise RuntimeError('Prepared target already exists')
    desired = transform(files, Path(__file__).resolve().parent)
    os.umask(0o077)
    output.mkdir(mode=0o700)
    manifest = []
    for relative, after in desired.items():
        for kind, content in [('before', files.get(relative)), ('files', after)]:
            if content is None:
                continue
            target = output / kind / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            target.chmod(0o600)
        manifest.append({'file': relative, 'before': EXPECTED.get(relative), 'after': hashlib.sha256(after.encode()).hexdigest()})
        if relative.endswith('.php'):
            subprocess.run(['/usr/bin/php', '-l', str(output / 'files' / relative)], check=True)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'prepared': True, 'changed_existing_files': len(files), 'new_files': 2, 'live_changed': False, 'migration_applied': False}))


if __name__ == '__main__':
    main()
