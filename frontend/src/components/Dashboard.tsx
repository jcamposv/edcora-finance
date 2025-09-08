import React, { useState, useEffect } from 'react';
import { transactionApi, userApi, stripeApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import BalanceCard from './BalanceCard';
import TransactionList from './TransactionList';
import ExpenseChart from './ExpenseChart';

interface DashboardProps {
  phoneNumber: string;
  onLogout: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({ phoneNumber, onLogout }) => {
  const [user, setUser] = useState(null);
  const [balance, setBalance] = useState<{ total: number; income: number; expenses: number }>({ 
    total: 0, 
    income: 0, 
    expenses: 0 
  });
  const [transactions, setTransactions] = useState([]);
  const [expensesByCategory, setExpensesByCategory] = useState([]);
  const [subscriptionStatus, setSubscriptionStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        setIsLoading(true);
        const userResponse = await userApi.getByPhone(phoneNumber);
        const userData = userResponse.data;
        setUser(userData);

        const [balanceResponse, transactionsResponse, expensesResponse, subscriptionResponse] = await Promise.all([
          transactionApi.getUserBalance(userData.id),
          transactionApi.getUserTransactions(userData.id, { limit: 10 }),
          transactionApi.getExpensesByCategory(userData.id),
          stripeApi.getSubscriptionStatus(userData.id).catch(() => ({ data: null }))
        ]);

        setBalance(balanceResponse.data);
        setTransactions(transactionsResponse.data);
        setExpensesByCategory(expensesResponse.data);
        setSubscriptionStatus(subscriptionResponse.data);
      } catch (err) {
        console.error('Error fetching user data:', err);
        setError('Error cargando datos del usuario');
      } finally {
        setIsLoading(false);
      }
    };

    fetchUserData();
  }, [phoneNumber]);

  const handleCreateCheckoutSession = async () => {
    try {
      const response = await stripeApi.createCheckoutSession(
        user.id,
        window.location.origin + '/dashboard?success=true',
        window.location.origin + '/dashboard?canceled=true'
      );
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Error creating checkout session:', error);
      setError('Error al crear sesión de pago');
    }
  };

  const handleCreatePortalSession = async () => {
    try {
      const response = await stripeApi.createPortalSession(user.id, window.location.origin + '/dashboard');
      window.location.href = response.data.portal_url;
    } catch (error) {
      console.error('Error creating portal session:', error);
      setError('Error al crear sesión de portal');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Cargando dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4">{error}</p>
            <Button onClick={onLogout} variant="outline" className="w-full">
              Volver al Login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isPremium = subscriptionStatus?.is_premium || false;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card/50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Control de Finanzas</h1>
              <p className="text-sm text-muted-foreground">
                Bienvenido, {user?.name || phoneNumber}
                {isPremium && <span className="ml-2 inline-flex items-center px-2 py-1 rounded-full text-xs bg-primary text-primary-foreground">Premium</span>}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {!isPremium && (
                <Button onClick={handleCreateCheckoutSession} className="hidden sm:inline-flex">
                  Actualizar a Premium
                </Button>
              )}
              {isPremium && (
                <Button onClick={handleCreatePortalSession} variant="outline" className="hidden sm:inline-flex">
                  Gestionar Suscripción
                </Button>
              )}
              <Button onClick={onLogout} variant="ghost">
                Cerrar Sesión
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        <BalanceCard balance={balance} />
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TransactionList transactions={transactions} />
          <ExpenseChart expensesByCategory={expensesByCategory} />
        </div>

        {!isPremium && (
          <Card className="border-primary/20 bg-primary/5">
            <CardHeader>
              <CardTitle className="text-primary">¿Quieres más funciones?</CardTitle>
              <CardDescription>
                Actualiza a Premium para obtener reportes automáticos, análisis avanzados y más.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-2">
                <Button onClick={handleCreateCheckoutSession} className="flex-1">
                  Actualizar a Premium - $9.99/mes
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
};

export default Dashboard;