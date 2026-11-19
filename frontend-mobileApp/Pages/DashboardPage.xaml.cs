using SalesMobileApp.Core;
using SalesMobileApp.ViewModels;
namespace SalesMobileApp.Pages;
public partial class DashboardPage : ContentPage
{
    private readonly DashboardViewModel _vm;
    public DashboardPage() { InitializeComponent(); _vm = new(ServiceLocator.Services.GetRequiredService<Services.ApiClient>(), ServiceLocator.Services.GetRequiredService<Services.SessionStore>()); _vm.OpenHistoryCommand = new(() => _vm.OpenHistoryAsync()); _vm.OpenProfileCommand = new(() => _vm.OpenProfileAsync()); _vm.OpenInvoiceCommand = new(() => Shell.Current.GoToAsync("invoice")); BindingContext = _vm; }
    protected override async void OnAppearing() { base.OnAppearing(); await _vm.LoadAsync(); }
}
