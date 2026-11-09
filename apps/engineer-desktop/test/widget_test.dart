import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:aegis_engineer_desktop/app/aegis_app.dart';

void main() {
  testWidgets('renders AEGIS engineer desktop navigation', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: AegisApp()));
    expect(find.text('AEGIS'), findsOneWidget);
    expect(find.text('SECURITY OPERATIONS'), findsOneWidget);
    expect(find.text('Operations Overview'), findsOneWidget);
    expect(find.text('Services not connected'), findsOneWidget);
  });
}
