import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';

class GpmLoginScreen extends StatefulWidget {
  final VoidCallback onSignedIn;

  const GpmLoginScreen({
    super.key,
    required this.onSignedIn,
  });

  @override
  State<GpmLoginScreen> createState() => _GpmLoginScreenState();
}

class _GpmLoginScreenState extends State<GpmLoginScreen> {
  final _usernameController = TextEditingController(text: 'admin');
  final _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  String _role = 'client';
  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _error;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final result = await gpmApi.login(
      username: _usernameController.text,
      password: _passwordController.text,
      role: _role,
    );

    if (!mounted) return;
    setState(() {
      _isLoading = false;
      _error = result['success'] == true
          ? null
          : result['error']?.toString() ?? 'Не удалось войти';
    });

    if (result['success'] == true) {
      widget.onSignedIn();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: GpmColors.page,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Image.asset(
                          'assets/images/gpm_logo.png',
                          width: 48,
                          height: 48,
                          fit: BoxFit.contain,
                        ),
                        const SizedBox(width: 10),
                        const Text(
                          'GPM',
                          style: TextStyle(
                            color: GpmColors.black,
                            fontSize: 34,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 28),
                    Text(
                      'Кто вы?',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 12),
                    Column(
                      children: [
                        for (final option in const [
                          (
                            'client',
                            'Я клиент',
                            Icons.business_center_outlined,
                          ),
                          (
                            'worker',
                            'Я исполнитель',
                            Icons.engineering_outlined,
                          ),
                          (
                            'logist',
                            'Я логист',
                            Icons.assignment_ind_outlined,
                          ),
                        ]) ...[
                          SizedBox(
                            width: double.infinity,
                            child: OutlinedButton.icon(
                              onPressed: () =>
                                  setState(() => _role = option.$1),
                              style: OutlinedButton.styleFrom(
                                alignment: Alignment.centerLeft,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 14,
                                ),
                                backgroundColor: _role == option.$1
                                    ? Theme.of(context)
                                        .colorScheme
                                        .primaryContainer
                                    : null,
                              ),
                              icon: Icon(option.$3),
                              label: Text(option.$2),
                            ),
                          ),
                          if (option.$1 != 'logist')
                            const SizedBox(height: 8),
                        ],
                      ],
                    ),
                    const SizedBox(height: 18),
                    TextFormField(
                      controller: _usernameController,
                      decoration: const InputDecoration(
                        labelText: 'Логин',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      textInputAction: TextInputAction.next,
                      validator: (value) =>
                          value == null || value.trim().isEmpty
                              ? 'Введите логин'
                              : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscurePassword,
                      decoration: InputDecoration(
                        labelText: 'Пароль',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          tooltip: _obscurePassword
                              ? 'Показать пароль'
                              : 'Скрыть пароль',
                          onPressed: () => setState(
                            () => _obscurePassword = !_obscurePassword,
                          ),
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                        ),
                      ),
                      onFieldSubmitted: (_) => _submit(),
                      validator: (value) =>
                          value == null || value.isEmpty
                              ? 'Введите пароль'
                              : null,
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _error!,
                        style: const TextStyle(
                          color: GpmColors.red,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    FilledButton.icon(
                      onPressed: _isLoading ? null : _submit,
                      icon: _isLoading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.login),
                      label: const Text('Войти'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
