class WorkerTransaction {
  final String id;
  final String title;
  final String date;
  final String amount;
  final bool isIncome;

  const WorkerTransaction({
    required this.id,
    required this.title,
    required this.date,
    required this.amount,
    required this.isIncome,
  });
}
