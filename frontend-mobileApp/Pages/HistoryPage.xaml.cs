using SalesMobileApp.Core; using SalesMobileApp.ViewModels;
namespace SalesMobileApp.Pages;
public partial class HistoryPage : ContentPage { private readonly HistoryViewModel _vm; public HistoryPage() { InitializeComponent(); _vm = new(ServiceLocator.Services.GetRequiredService<Services.ApiClient>(), ServiceLocator.Services.GetRequiredService<Services.SessionStore>()); BindingContext = _vm; } protected override async void OnAppearing() { base.OnAppearing(); await _vm.LoadAsync(); } }
