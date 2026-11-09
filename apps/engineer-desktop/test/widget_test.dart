import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:aegis_engineer_desktop/app/aegis_app.dart';

void main() {
  testWidgets('renders the AEGIS engineer workstation overview', (tester) async {
    await tester.view.setPhysicalSize(const Size(1440, 1000));
    await tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const ProviderScope(child: AegisApp()));

    expect(find.text('AEGIS'), findsOneWidget);
    expect(find.text('SECURITY OPERATIONS'), findsOneWidget);
    expect(find.text('Operations overview'), findsOneWidget);
    expect(find.text('Threat landscape'), findsOneWidget);
    expect(find.text('Priority queue'), findsOneWidget);
    expect(find.text('Integration health'), findsOneWidget);
    expect(find.text('NOT CONNECTED'), findsOneWidget);
    expect(find.text('Waiting for security telemetry'), findsOneWidget);
  });

  testWidgets('does not fabricate operational metrics while disconnected', (tester) async {
    await tester.view.setPhysicalSize(const Size(1440, 1000));
    await tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const ProviderScope(child: AegisApp()));

    expect(find.text('OPEN ALERTS'), findsOneWidget);
    expect(find.text('CRITICAL FINDINGS'), findsOneWidget);
    expect(find.text('PROTECTED ASSETS'), findsOneWidget);
    expect(find.text('0'), findsOneWidget);
    expect(find.text('—'), findsNWidgets(3));
  });
}
