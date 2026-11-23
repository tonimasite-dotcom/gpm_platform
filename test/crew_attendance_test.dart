import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/screens/attendance/crew_attendance.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'support/load_test_fonts.dart';

class CrewFakeApi extends GpmApiService {
  Map<String, dynamic> state;
  final calls = <Map<String,dynamic>>[];
  CrewFakeApi(this.state);
  @override
  Future<Map<String,dynamic>> getCrewAttendance(String orderId) async =>
    Map<String,dynamic>.from(jsonDecode(jsonEncode(state)) as Map);
  @override
  Future<Map<String,dynamic>> crewAttendanceRequest(String path, {
    String method='POST', Map<String,dynamic>? body,
  }) async {
    calls.add({'path':path,'method':method,'body':body});
    if (path.endsWith('/presence')) return {
      'kind':'presence','evidence_id':'synthetic-proof','verifier_mode':'crew_scan',
      'confirmation_url':'gpm-crew-presence:synthetic-token',
      'expires_at':DateTime.now().add(const Duration(seconds:60)).toIso8601String(),
    };
    if (path.contains('/crew-reviews/')) {
      state['proofs']=[];
      return {'success':true};
    }
    return {'success':true,'status':'awaiting_confirmation'};
  }
}

Map<String,dynamic> fixture({bool logist=false,bool leader=true,bool pending=false}) => {
  'enabled':true,'paused':false,'role':logist?'logist':'worker',
  'is_leader':!logist&&leader,'mode':'crew','leader_account_id':'leader',
  'roster':[
    {'worker_account_id':'leader','worker_name':'Тестовый старший','is_leader':true,
      'check_in_at':null,'check_out_at':null},
    {'worker_account_id':'worker','worker_name':'Тестовый исполнитель','is_leader':false,
      'check_in_at':null,'check_out_at':null},
  ],
  'proofs':pending?[
    {'evidence_id':'synthetic-proof','worker_account_id':'worker','worker_name':'Тестовый исполнитель',
      'action':'check_in','status':'pending_review','geo_status':'review',
      'collected_at':'2026-11-23T08:00:00Z',
      'worker_evidence':{'reason':'Геолокация недоступна'},
      'scanner_evidence':{'distance_m':20,'accuracy':8,'reason':''}},
  ]:[],
  'session':!logist&&leader?{
    'session_id':'synthetic-session','action':'check_in','status':'collecting',
    'members':[
      {'worker_name':'Тестовый старший','geo_status':'valid','collected_at':'2026-11-23T08:00:00Z'},
      {'worker_name':'Тестовый исполнитель','geo_status':'review','collected_at':'2026-11-23T08:03:00Z'},
    ],
  }:null,
};

Widget host(Widget child) => MaterialApp(
  debugShowCheckedModeBanner:false,theme:buildGpmTheme(),
  home:Scaffold(appBar:AppBar(title:const Text('Табель')),body:SingleChildScrollView(
    padding:const EdgeInsets.all(14),child:child)),
);

Future<void> capture(WidgetTester tester,GlobalKey key,String name) async {
  await tester.runAsync(() async {
    final boundary=key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final image=await boundary.toImage(pixelRatio:1);
    final data=await image.toByteData(format:ui.ImageByteFormat.png);
    final file=File('build/crew-attendance-shots/$name.png');
    await file.parent.create(recursive:true);
    await file.writeAsBytes(data!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  setUpAll(loadMobileTestFonts);
  setUp(()=>dotenv.testLoad(fileInput:'GPM_APP_MODE=demo\n'));
  testWidgets('disabled feature preserves the existing attendance interface',(tester) async {
    app.gpmApi=CrewFakeApi({'enabled':false});
    await tester.pumpWidget(host(const CrewAttendanceGate(orderId:'test',child:Text('Прежний табель'))));
    await tester.pumpAndSettle();
    expect(find.text('Прежний табель'),findsOneWidget);
  });
  testWidgets('worker submits denied geolocation for review, not a fabricated point',(tester) async {
    final api=CrewFakeApi(fixture(leader:false));
    app.gpmApi=api;
    await tester.pumpWidget(host(CrewAttendanceGate(orderId:'test',
      locationProvider:() async=>{'error':'denied'},child:const Text('legacy'))));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('crew_presence')));
    await tester.tap(find.byKey(const Key('crew_presence')));
    await tester.pumpAndSettle();
    expect(find.text('QR для старшего'),findsOneWidget);
    expect(api.calls.single['body'],{'location':{'error':'denied'}});
    expect(api.calls.any((c)=>c['path'].toString().contains('confirm')),isFalse);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('manual approval requires an explicit reason and carries no editable time',(tester) async {
    final api=CrewFakeApi(fixture(logist:true,pending:true));
    app.gpmApi=api;
    await tester.pumpWidget(host(const CrewAttendanceGate(orderId:'test',child:Text('legacy'))));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Подтвердить'));
    await tester.tap(find.text('Подтвердить'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('crew_review_reason')),'Присутствие проверено');
    await tester.tap(find.text('Сохранить решение'));
    await tester.pumpAndSettle();
    expect(api.calls.single['body'],{'decision':'approve','reason':'Присутствие проверено'});
    expect(api.state['proofs'],isEmpty);
    expect(tester.takeException(),isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  for(final width in [390.0,1280.0,320.0]) {
    for(final logist in [false,true]) {
      testWidgets('crew attendance fits $width logist=$logist',(tester) async {
        tester.view.physicalSize=Size(width,900);
        tester.view.devicePixelRatio=1;
        tester.platformDispatcher.textScaleFactorTestValue=width==320?2:1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        app.gpmApi=CrewFakeApi(fixture(logist:logist,pending:logist));
        final key=GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key:key,child:host(
          const CrewAttendanceGate(orderId:'test',child:Text('legacy')))));
        await tester.pumpAndSettle();
        expect(tester.takeException(),isNull);
        expect(find.byType(Checkbox),findsNothing);
        await capture(tester,key,'crew_${width.toInt()}_$logist');
        await tester.pumpWidget(const SizedBox.shrink());
      });
    }
  }
}
