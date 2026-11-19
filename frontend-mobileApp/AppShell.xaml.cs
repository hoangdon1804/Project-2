namespace SalesMobileApp;

public partial class AppShell : Shell
{
    public AppShell()
    {
        InitializeComponent();
        Routing.RegisterRoute("dashboard", typeof(Pages.DashboardPage));
        Routing.RegisterRoute("history", typeof(Pages.HistoryPage));
        Routing.RegisterRoute("profile", typeof(Pages.ProfilePage));
        Routing.RegisterRoute("invoice", typeof(Pages.InvoicePage));
    }
}
