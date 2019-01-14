function reload() {
  reloadDb();
  reloadTable("Backlog");
  reloadTable("WIP");
  reloadTable("Done");
}
